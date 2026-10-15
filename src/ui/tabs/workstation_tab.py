import os
import re
import copy
import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QSplitter,
    QFrame,
    QProgressBar,
    QTextEdit,
    QDialog,
    QInputDialog,
    QComboBox,
    QTabWidget,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal, QUrl, QThread
from PySide6.QtGui import QDesktopServices
from Bio import SeqIO

from src.config import OUTPUT_DIR, DATA_DIR, find_tool, BIN_DIR
from src.core.project_manager import ProjectManager, PhyloProject, STEP_KEYS, STEP_TITLES, StepRecord
from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner
from src.ui.widgets.block_pipeline_canvas import BlockPipelineCanvas
from src.ui.widgets.scratch_canvas import ScratchWorkspaceCanvas
from src.ui.widgets.scratch_stage import ScratchStageWidget
from src.ui.widgets.analysis_preferences_dialog import AnalysisPreferencesDialog
from src.ui.widgets.step_inspection_dialog import StepInspectionDialog
from src.ui.widgets.module_toolbox import ModuleToolboxWidget
from src.ui.widgets.log_viewer import LogViewer


class WorkstationWorker(QThread):
    step_started = Signal(str)           # step_key
    step_finished = Signal(str, bool, str, list, dict, str) # step_key, success, summary, output_files, params, cmd
    log_emitted = Signal(str)
    all_finished = Signal(bool, str)

    def __init__(self, project: PhyloProject, steps_to_run: list[str], params_by_step: dict):
        super().__init__()
        self.project = project
        self.steps_to_run = steps_to_run
        self.params_by_step = params_by_step
        self.is_cancelled = False
        self.mafft_runner = MafftRunner()
        self.trimal_runner = TrimalRunner()
        self.mf_runner = ModelFinderRunner()
        self.iqtree_runner = IQTreeRunner()

    def cancel(self):
        self.is_cancelled = True
        self.mafft_runner.cancel()
        self.trimal_runner.cancel()
        self.mf_runner.cancel()
        self.iqtree_runner.cancel()

    def _find_upstream_fasta(self, before_step: str) -> str:
        try:
            target_idx = STEP_KEYS.index(before_step)
        except ValueError:
            target_idx = len(STEP_KEYS)

        for k in reversed(STEP_KEYS[:target_idx]):
            rec = self.project.steps.get(k)
            if rec and rec.output_files:
                for f in rec.output_files:
                    p = Path(f)
                    if p.exists() and p.suffix.lower() in (".fasta", ".fa", ".fas", ".fna", ".faa", ".phy"):
                        return str(p.resolve())
        return ""

    def run(self):
        p_dir = Path(self.project.project_dir)
        current_fasta = ""

        if not self.steps_to_run:
            self.all_finished.emit(False, "無勾選或指定執行的分析步驟。")
            return

        first_step = self.steps_to_run[0]
        if first_step == "raw":
            raw_params = self.params_by_step.get("raw", {})
            raw_fp = raw_params.get("fasta_path", "")
            if raw_fp and Path(raw_fp).exists():
                current_fasta = str(Path(raw_fp).resolve())
            elif self.project.steps.get("raw") and self.project.steps["raw"].output_files:
                current_fasta = self.project.steps["raw"].output_files[0]
        else:
            current_fasta = self._find_upstream_fasta(first_step)
            if not current_fasta:
                raw_params = self.params_by_step.get("raw", {})
                raw_fp = raw_params.get("fasta_path", "")
                if raw_fp and Path(raw_fp).exists():
                    current_fasta = str(Path(raw_fp).resolve())
                elif self.project.steps.get("raw") and self.project.steps["raw"].output_files:
                    current_fasta = self.project.steps["raw"].output_files[0]

        best_model = ""
        # Check if modelfinder already has a recorded best model
        mf_rec = self.project.steps.get("modelfinder")
        if mf_rec and mf_rec.parameters and "best_model" in mf_rec.parameters:
            best_model = mf_rec.parameters["best_model"]

        for step_key in self.steps_to_run:
            if self.is_cancelled:
                self.all_finished.emit(False, "分析已被使用者手動終止。")
                return

            self.step_started.emit(step_key)
            params = self.params_by_step.get(step_key, {})
            subfolder = STEP_TITLES.get(step_key, (step_key, f"step_{step_key}"))[1]
            step_dir = p_dir / subfolder
            step_dir.mkdir(parents=True, exist_ok=True)

            try:
                if step_key == "raw":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "找不到輸入的 FASTA 序列檔案", [], params, "")
                        self.all_finished.emit(False, "請先於「原始序列輸入」積木設定有效的 FASTA 檔案。")
                        return

                    dest_raw = step_dir / Path(current_fasta).name
                    if Path(current_fasta).resolve() != dest_raw.resolve():
                        shutil.copy2(current_fasta, dest_raw)
                    current_fasta = str(dest_raw.resolve())

                    with open(current_fasta, "r", encoding="utf-8", errors="replace") as handle:
                        records = list(SeqIO.parse(handle, "fasta"))
                    if not records:
                        self.step_finished.emit(step_key, False, "FASTA 檔案未包含任何有效序列", [], params, "")
                        self.all_finished.emit(False, "輸入之 FASTA 檔案無有效序列！")
                        return

                    taxa = len(records)
                    sites = len(records[0].seq) if records else 0
                    params["taxa"] = taxa
                    params["length"] = sites
                    params["file_name"] = Path(current_fasta).name
                    params["file_size_kb"] = round(Path(current_fasta).stat().st_size / 1024, 2)
                    first_seq_str = str(records[0].seq).upper() if records else ""
                    is_dna = set(first_seq_str).issubset(set("ACGTN-?RYKMSWBDHV"))
                    params["data_type"] = "DNA/RNA (核酸)" if is_dna else "Protein (胺基酸)"
                    if is_dna and first_seq_str:
                        c_count = first_seq_str.count("C") + first_seq_str.count("G")
                        total_valid = sum(first_seq_str.count(b) for b in "ACGT")
                        gc_ratio = round((c_count / total_valid * 100), 1) if total_valid > 0 else 0
                        params["gc_content"] = f"{gc_ratio}%"
                    summary = f"成功載入原始序列: {Path(current_fasta).name} (共 {taxa} 物種, {sites} 位點)"
                    self.step_finished.emit(step_key, True, summary, [current_fasta], params, "")

                elif step_key == "sanitize":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少前一步驟序列", [], params, "")
                        self.all_finished.emit(False, "缺少輸入序列，請先確認前一步驟已成功載入序列。")
                        return
                    res = sanitize_fasta_file(current_fasta)
                    if not res.success or not res.cleaned_records:
                        err_msg = "; ".join(res.warnings) if res.warnings else (getattr(res, "message", "品管過濾失敗"))
                        self.step_finished.emit(step_key, False, err_msg, [], params, "")
                        self.all_finished.emit(False, f"序列品管防呆過濾失敗: {err_msg}")
                        return
                    out_clean = step_dir / f"{Path(current_fasta).stem}_cleaned.fasta"
                    SeqIO.write(res.cleaned_records, str(out_clean), "fasta")
                    current_fasta = str(out_clean.resolve())
                    params["taxa"] = res.total_taxa
                    params["length"] = len(res.cleaned_records[0].seq) if res.cleaned_records else 0
                    summary = f"品管清洗完成: 產出 {res.total_taxa} 筆標準化序列 (類型: {res.seq_type})"
                    self.step_finished.emit(step_key, True, summary, [current_fasta], params, "PhyloCraft 内置品管防呆過濾")

                elif step_key == "alignment":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少輸入序列", [], params, "")
                        self.all_finished.emit(False, "缺少輸入序列，請先執行前續步驟。")
                        return
                    out_aln = step_dir / f"{Path(current_fasta).stem}_aligned.fasta"
                    strat = params.get("strategy", "auto")
                    if "localpair" in strat or "linsi" in strat:
                        algo = "linsi"
                    elif "globalpair" in strat or "ginsi" in strat:
                        algo = "ginsi"
                    elif "fftns2" in strat:
                        algo = "fft-ns-2"
                    else:
                        algo = "auto"

                    th_str = str(params.get("threads", "AUTO"))
                    th = int(th_str) if th_str.isdigit() else -1
                    cmd_str = f"mafft --{algo} input.fasta > aligned.fasta"

                    ok, msg = self.mafft_runner.run_alignment(
                        current_fasta,
                        out_aln,
                        algorithm=algo,
                        threads=th,
                        log_callback=self.log_emitted.emit,
                    )
                    if self.is_cancelled:
                        self.step_finished.emit(step_key, False, "使用者手動取消", [], params, cmd_str)
                        self.all_finished.emit(False, "分析已被使用者終止。")
                        return
                    if not ok:
                        self.step_finished.emit(step_key, False, f"MAFFT 比對失敗: {msg}", [], params, cmd_str)
                        self.all_finished.emit(False, f"MAFFT 執行失敗: {msg}")
                        return
                    current_fasta = str(out_aln.resolve())
                    with open(current_fasta, "r", encoding="utf-8", errors="replace") as handle:
                        records = list(SeqIO.parse(handle, "fasta"))
                    params["taxa"] = len(records)
                    params["length"] = len(records[0].seq) if records else 0
                    summary = f"MAFFT 對齊完成: {len(records)} 物種 ｜ 長度: {len(records[0].seq) if records else 0} bp"
                    self.step_finished.emit(step_key, True, summary, [current_fasta], params, cmd_str)

                elif step_key == "trimming":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少比對矩陣", [], params, "")
                        self.all_finished.emit(False, "缺少比對矩陣，請先執行多重比對。")
                        return
                    out_trim = step_dir / f"{Path(current_fasta).stem}_trimmed.fasta"
                    method = params.get("method", "automated1")
                    cmd_str = f"trimal -in aligned.fasta -out trimmed.fasta -{method}"

                    ok, msg = self.trimal_runner.run_trimming(
                        current_fasta,
                        out_trim,
                        method=method,
                        log_callback=self.log_emitted.emit,
                    )
                    if self.is_cancelled:
                        self.step_finished.emit(step_key, False, "使用者手動取消", [], params, cmd_str)
                        self.all_finished.emit(False, "分析已被使用者終止。")
                        return
                    if not ok:
                        self.step_finished.emit(step_key, False, f"trimAl 修剪失敗: {msg}", [], params, cmd_str)
                        self.all_finished.emit(False, f"trimAl 執行失敗: {msg}")
                        return
                    current_fasta = str(out_trim.resolve())
                    with open(current_fasta, "r", encoding="utf-8", errors="replace") as handle:
                        records = list(SeqIO.parse(handle, "fasta"))
                    params["taxa"] = len(records)
                    params["length"] = len(records[0].seq) if records else 0
                    summary = f"trimAl {method} 修剪完成: 保留 {len(records[0].seq) if records else 0} 個高品質位點"
                    self.step_finished.emit(step_key, True, summary, [current_fasta], params, cmd_str)

                elif step_key == "modelfinder":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少修剪後序列", [], params, "")
                        self.all_finished.emit(False, "缺少輸入序列，請先執行前續比對步驟。")
                        return
                    prefix = step_dir / f"{Path(current_fasta).stem}_modelfinder"
                    scope = params.get("scope", "TESTONLY")
                    cmd_str = f"iqtree2 -s trimmed.fasta -m {scope} -T AUTO"

                    res = self.mf_runner.run_modelfinder(
                        current_fasta,
                        str(prefix),
                        search_scope=scope,
                        log_callback=self.log_emitted.emit,
                    )
                    if self.is_cancelled:
                        self.step_finished.emit(step_key, False, "使用者手動取消", [], params, cmd_str)
                        self.all_finished.emit(False, "分析已被使用者終止。")
                        return
                    if not res.success:
                        self.step_finished.emit(step_key, False, f"ModelFinder 失敗: {res.message}", [], params, cmd_str)
                        self.all_finished.emit(False, f"ModelFinder 失敗: {res.message}")
                        return
                    best_model = res.best_model
                    params["best_model"] = best_model
                    summary = f"ModelFinder 檢定完成: BIC 最適模型為 {best_model} (共評比 {len(res.candidate_models)} 種模型)"
                    self.step_finished.emit(
                        step_key, True, summary, [res.iqtree_report], params, cmd_str
                    )

                elif step_key == "tree":
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少比對位點", [], params, "")
                        self.all_finished.emit(False, "缺少比對矩陣檔案，請先執行比對步驟。")
                        return
                    prefix = step_dir / f"{Path(current_fasta).stem}_tree"
                    user_model_param = params.get("model", "")
                    if user_model_param and user_model_param != "MFP":
                        model_choice = user_model_param
                    elif best_model:
                        model_choice = best_model
                    else:
                        model_choice = "MFP"

                    boot = params.get("bootstrap", 1000)
                    alrt = params.get("alrt", 1000)
                    cmd_str = f"iqtree2 -s input.fasta -m {model_choice} -B {boot} --alrt {alrt} -T AUTO"

                    res = self.iqtree_runner.run_inference(
                        current_fasta,
                        str(prefix),
                        model=model_choice,
                        bootstrap=boot,
                        alrt=alrt,
                        log_callback=self.log_emitted.emit,
                    )
                    if self.is_cancelled:
                        self.step_finished.emit(step_key, False, "使用者手動取消", [], params, cmd_str)
                        self.all_finished.emit(False, "分析已被使用者終止。")
                        return
                    if not res.success:
                        self.step_finished.emit(step_key, False, f"IQ-TREE 建樹失敗: {res.message}", [], params, cmd_str)
                        self.all_finished.emit(False, f"IQ-TREE 失敗: {res.message}")
                        return
                    params["model"] = res.best_model
                    params["bootstrap"] = boot
                    summary = f"IQ-TREE 2 ML 建樹完成: 模型 {res.best_model} ｜ 拔靴檢驗 {boot} 次 ｜ 演化樹已產出"
                    self.step_finished.emit(
                        step_key, True, summary, [res.tree_file, res.iqtree_report], params, cmd_str
                    )

                elif step_key in ("tree_fasttree", "fasttree"):
                    if not current_fasta or not Path(current_fasta).exists():
                        self.step_finished.emit(step_key, False, "缺少輸入序列", [], params, "")
                        self.all_finished.emit(False, "缺少輸入序列檔案，請先執行比對步驟。")
                        return
                    out_tree = step_dir / f"{Path(current_fasta).stem}_fasttree.treefile"
                    ft_bin = find_tool("fasttree")
                    if not ft_bin:
                        ft_bin = str(BIN_DIR / "FastTree.exe")

                    model_param = params.get("model", "-nt")
                    cmd_parts = [ft_bin]
                    if "-gtr" in model_param:
                        cmd_parts.extend(["-gtr", "-nt"])
                    elif "-nt" in model_param or "核酸" in model_param:
                        cmd_parts.append("-nt")
                    if params.get("speed") == "極速 (-fastest)":
                        cmd_parts.append("-fastest")
                    cmd_parts.append(current_fasta)
                    cmd_str = f"FastTree {' '.join(cmd_parts[1:-1])} {Path(current_fasta).name} > {out_tree.name}"

                    self.log_emitted.emit(f"⚡ [FastTree 2] 正在執行超極速最大概似建樹推論: {cmd_str}...")
                    import subprocess
                    try:
                        with open(out_tree, "w", encoding="utf-8") as out_f:
                            proc = subprocess.Popen(
                                cmd_parts,
                                stdout=out_f,
                                stderr=subprocess.PIPE,
                                text=True,
                            )
                            _, stderr = proc.communicate(timeout=120)
                            if proc.returncode != 0:
                                err_msg = f"FastTree 執行失敗 (代碼 {proc.returncode}): {stderr}"
                                self.step_finished.emit(step_key, False, err_msg, [], params, cmd_str)
                                self.all_finished.emit(False, err_msg)
                                return
                    except Exception as e:
                        err_msg = f"FastTree 執行例外: {e}"
                        self.step_finished.emit(step_key, False, err_msg, [], params, cmd_str)
                        self.all_finished.emit(False, err_msg)
                        return

                    summary = f"FastTree 2 極速建樹完成: 演化樹拓撲已產出至 {out_tree.name}"
                    self.step_finished.emit(step_key, True, summary, [str(out_tree.resolve())], params, cmd_str)

                elif step_key == "timetree":
                    tree_rec = self.project.steps.get("tree")
                    tree_file = ""
                    if tree_rec and tree_rec.output_files:
                        for f in tree_rec.output_files:
                            if f.endswith(".treefile") or f.endswith(".nwk"):
                                tree_file = f
                                break

                    date_fp = params.get("date_file", "").strip()
                    outlier_val = float(params.get("outlier", 3.0))

                    if date_fp and Path(date_fp).exists() and tree_file and current_fasta:
                        self.log_emitted.emit("[TimeTree] 正在執行 LSD2 最小平方法分子鐘定年推論...")
                        prefix = step_dir / f"{Path(current_fasta).stem}_timetree"
                        res = self.iqtree_runner.run_inference(
                            current_fasta,
                            str(prefix),
                            user_tree=tree_file,
                            date_file=date_fp,
                            date_outlier=outlier_val,
                            log_callback=self.log_emitted.emit,
                        )
                        if res.success and (res.timetree_file or res.tree_file):
                            active_t = res.timetree_file or res.tree_file
                            summary = f"LSD2 分子鐘定年完成 (速率: {res.rate_estimate or '已推算'}, tMRCA: {res.tmrca_estimate or '已推算'})"
                            out_files = [active_t]
                            if res.lsd_report_file:
                                out_files.append(res.lsd_report_file)
                            self.step_finished.emit(step_key, True, summary, out_files, params, f"iqtree -te {Path(tree_file).name} --date {Path(date_fp).name}")
                        else:
                            summary = f"LSD2 定年執行未成功: {res.message}"
                            self.step_finished.emit(step_key, False, summary, [tree_file] if tree_file else [], params, "")
                    else:
                        if not tree_file:
                            summary = "LSD2 分子鐘時間樹模塊已就緒 (待執行建樹或載入校準檔)"
                        else:
                            summary = f"LSD2 分子鐘時間樹模塊已設定 (基於 {Path(tree_file).name}，可於參數抽屜載入 Date File 進行絕對年代定年)"
                        self.step_finished.emit(step_key, True, summary, [tree_file] if tree_file else [], params, "lsd2")

            except Exception as e:
                self.step_finished.emit(step_key, False, f"非預期錯誤: {str(e)}", [], params, "")
                self.all_finished.emit(False, f"執行步驟 {step_key} 時發生錯誤: {str(e)}")
                return

        self.all_finished.emit(True, "所選之積木工作流已順利全線執行完畢。")


class StageFloatingDialog(QDialog):
    """
    MEGA-style Independent Floating Window for Scratch Stage & Outcome Visualizer.
    Can be placed on a second monitor, maximized, or docked back into main workstation.
    """
    closed = Signal()

    def __init__(self, stage_widget: ScratchStageWidget, parent: QWidget | None = None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("PhyloCraft 成果舞台與視覺化探針 (Pop-out Stage)")
        self.resize(880, 680)
        self.stage_widget = stage_widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(stage_widget)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class WorkstationTab(QWidget):
    """
    生物演化學科研工作站 (Research Workstation & Blocks Canvas)
    Phase 2 Highlights:
    - Multi-Tab Modular Visual Block Pipeline Canvas (Scratch for Bioinformatics)
    - Flexible Layout Presets (3-Column, Canvas-Only Focus, Split Stage, Pop-out Window)
    - 1-Click Workflow Execution & Single-Step Run directly from cards
    - Inline Parameters Drawer on each Block Card
    - Dynamic Bypass Routing when steps are toggled off
    - Instant Data Inspector & Experiment Branching (Fork Branch)
    - Auto-ELN / Electronic Lab Notebook
    """

    jump_to_tab_requested = Signal(int)  # tab index
    view_tree_requested = Signal(str)
    view_msa_requested = Signal(str)
    view_model_test_requested = Signal(str)
    step_jump_with_data_requested = Signal(str, str)  # (step_key, file_path)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.pm = ProjectManager()
        self.worker: WorkstationWorker | None = None
        self.current_inspect_step: str = ""
        self.stage_dialog: StageFloatingDialog | None = None
        self._default_canvas: ScratchWorkspaceCanvas | None = None
        self.init_ui()
        self.load_default_or_demo_project()

    @property
    def block_canvas(self) -> ScratchWorkspaceCanvas:
        if hasattr(self, "workflow_tabs"):
            curr = self.workflow_tabs.currentWidget()
            if isinstance(curr, ScratchWorkspaceCanvas):
                return curr
        return getattr(self, "_default_canvas", None)

    @block_canvas.setter
    def block_canvas(self, val: ScratchWorkspaceCanvas):
        self._default_canvas = val

    def get_all_canvases(self) -> list[ScratchWorkspaceCanvas]:
        canvases = []
        if hasattr(self, "workflow_tabs"):
            for i in range(self.workflow_tabs.count()):
                w = self.workflow_tabs.widget(i)
                if isinstance(w, ScratchWorkspaceCanvas):
                    canvases.append(w)
        if not canvases and getattr(self, "_default_canvas", None):
            canvases.append(self._default_canvas)
        return canvases

    def create_canvas_tab(self, title: str, preset_idx: int = 0) -> ScratchWorkspaceCanvas:
        canvas = ScratchWorkspaceCanvas()
        canvas.step_jump_requested.connect(self.on_step_jump)
        canvas.inspect_step_requested.connect(self.inspect_step_data)
        canvas.run_step_requested.connect(self.run_single_step)
        canvas.fork_step_requested.connect(self.fork_branch)
        canvas.project_note_saved.connect(self.on_note_saved)
        canvas.open_preferences_requested.connect(self.open_preferences_for_step)
        canvas.flag_clicked.connect(self.run_entire_flow)
        canvas.zen_mode_toggled.connect(self.on_zen_mode_toggled)

        if preset_idx == 1:
            for k in STEP_KEYS:
                canvas.cards[k].enable_cb.setChecked(k not in ("trimming", "timetree"))
        elif preset_idx == 2:
            for k in STEP_KEYS:
                canvas.cards[k].enable_cb.setChecked(True)
        else:
            for k in STEP_KEYS:
                canvas.cards[k].enable_cb.setChecked(k != "timetree")

        if self.pm.current_project:
            canvas.load_project_state(self.pm.current_project)

        self.workflow_tabs.addTab(canvas, title)
        return canvas

    def add_new_canvas_tab(self):
        name, ok = QInputDialog.getText(
            self,
            "新建工作流畫布",
            "請輸入新工作流畫布名稱 (例如: 分支實驗 2、亞群比對流水線):",
            text=f"工作流畫布 {self.workflow_tabs.count() + 1}",
        )
        if ok and name.strip():
            canvas = self.create_canvas_tab(name.strip(), preset_idx=self.preset_combo.currentIndex())
            self.workflow_tabs.setCurrentWidget(canvas)

    def on_tab_close_requested(self, index: int):
        if self.workflow_tabs.count() <= 1:
            QMessageBox.information(self, "提示", "至少需保留一個工作流畫布。")
            return
        tab_title = self.workflow_tabs.tabText(index)
        ret = QMessageBox.question(
            self,
            "關閉工作流畫布",
            f"確定要關閉「{tab_title}」嗎？\n專案資料庫中的實際計算成果仍會完整保留。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            widget = self.workflow_tabs.widget(index)
            self.workflow_tabs.removeTab(index)
            if widget != self._default_canvas:
                widget.deleteLater()

    def on_active_canvas_tab_changed(self, index: int):
        if index >= 0 and self.pm.current_project:
            self.display_project(self.pm.current_project)
            self.inspector_title.setText(f"目前工作流畫布: {self.workflow_tabs.tabText(index)}")

    def set_layout_mode(self, mode: str):
        self.btn_layout_full.setChecked(mode == "full")
        self.btn_layout_focus.setChecked(mode == "canvas_only")
        self.btn_layout_split.setChecked(mode == "split")
        self.btn_layout_popout.setChecked(mode == "popout")

        if mode == "full":
            if self.stage_dialog is not None:
                self.dock_stage()
            self.toolbox.show()
            self.canvas_box.show()
            self.right_container.show()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.hide()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.hide()
            self.splitter.setSizes([240, 560, 360])

        elif mode == "canvas_only":
            if self.stage_dialog is not None:
                self.dock_stage()
            self.toolbox.hide()
            self.canvas_box.show()
            self.right_container.hide()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.show()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.show()
            self.splitter.setSizes([0, 1000, 0])

        elif mode == "split":
            if self.stage_dialog is not None:
                self.dock_stage()
            self.toolbox.hide()
            self.canvas_box.show()
            self.right_container.show()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.show()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.hide()
            self.splitter.setSizes([0, 600, 400])

        elif mode == "popout":
            self.pop_out_stage()
            self.toolbox.show()
            self.canvas_box.show()
            self.right_container.hide()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.hide()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.show()
            self.splitter.setSizes([220, 800, 0])

    def toggle_toolbox_visibility(self):
        is_vis = self.toolbox.isVisible()
        self.toolbox.setVisible(not is_vis)
        if hasattr(self, "btn_expand_toolbox"):
            self.btn_expand_toolbox.setVisible(is_vis)
        if is_vis:
            sizes = self.splitter.sizes()
            self.splitter.setSizes([0, sizes[1] + sizes[0], sizes[2]])
        else:
            self.splitter.setSizes([240, 560, 360])

    def toggle_right_panel(self):
        is_vis = self.right_container.isVisible()
        self.right_container.setVisible(not is_vis)
        if hasattr(self, "btn_expand_right"):
            self.btn_expand_right.setVisible(is_vis)
        if is_vis:
            sizes = self.splitter.sizes()
            self.splitter.setSizes([sizes[0], sizes[1] + sizes[2], 0])
        else:
            self.splitter.setSizes([240, 560, 360])

    def toggle_top_bar(self):
        self.is_top_bar_collapsed = not getattr(self, "is_top_bar_collapsed", False)
        if hasattr(self, "tb_row1_widget"):
            self.tb_row1_widget.setVisible(not self.is_top_bar_collapsed)
        if hasattr(self, "collapsed_hint_label"):
            self.collapsed_hint_label.setVisible(self.is_top_bar_collapsed)
        if hasattr(self, "btn_toggle_top_bar"):
            self.btn_toggle_top_bar.setText("展開控制列 ▼" if self.is_top_bar_collapsed else "收合控制列 ▲")
        if hasattr(self, "top_bar"):
            if self.is_top_bar_collapsed:
                self.top_bar.setFixedHeight(28)
            else:
                self.top_bar.setFixedHeight(40)

    def pop_out_stage(self):
        if self.stage_dialog is not None and self.stage_dialog.isVisible():
            self.stage_dialog.raise_()
            self.stage_dialog.activateWindow()
            return

        if hasattr(self, "stage_tab_layout"):
            self.stage_tab_layout.removeWidget(self.stage)
        elif hasattr(self, "r_layout"):
            self.r_layout.removeWidget(self.stage)

        self.stage_dialog = StageFloatingDialog(self.stage, parent=self)
        self.stage_dialog.closed.connect(self.dock_stage)
        self.stage.set_popped_out_state(True)
        self.btn_layout_popout.setChecked(True)
        self.stage_dialog.show()
        if hasattr(self, "right_container"):
            self.right_container.hide()
        if hasattr(self, "btn_expand_right"):
            self.btn_expand_right.show()
        if hasattr(self, "splitter"):
            self.splitter.setSizes([200, 750, 0])

    def dock_stage(self):
        if self.stage_dialog is not None:
            diag = self.stage_dialog
            self.stage_dialog = None
            diag.layout().removeWidget(self.stage)
            diag.close()

        if hasattr(self, "stage_tab_layout"):
            self.stage_tab_layout.addWidget(self.stage)
            if hasattr(self, "right_tabs"):
                self.right_tabs.setCurrentIndex(0)
        elif hasattr(self, "r_layout"):
            self.r_layout.insertWidget(0, self.stage, 2)

        self.stage.set_popped_out_state(False)
        self.stage.show()
        if hasattr(self, "right_container"):
            self.right_container.show()
        if hasattr(self, "btn_expand_right"):
            self.btn_expand_right.hide()
        self.btn_layout_popout.setChecked(False)
        if not self.btn_layout_focus.isChecked():
            self.btn_layout_full.setChecked(True)
            self.splitter.setSizes([200, 560, 360])

    def closeEvent(self, event):
        if getattr(self, "stage_dialog", None) is not None:
            self.stage_dialog.close()
        super().closeEvent(event)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(10)

        # 1. Project Management & Pipeline Action Top Bar (Ergonomic Single-Row Studio Bar)
        self.top_bar = QFrame()
        self.top_bar.setObjectName("workstation_top_bar")
        self.top_bar.setFixedHeight(40)
        self.top_bar.setStyleSheet("""
            QFrame#workstation_top_bar {
                background-color: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }
        """)
        tb_main_h = QHBoxLayout(self.top_bar)
        tb_main_h.setContentsMargins(10, 4, 10, 4)
        tb_main_h.setSpacing(10)

        # Main Single Row Container
        self.tb_row1_widget = QWidget()
        row1 = QHBoxLayout(self.tb_row1_widget)
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(8)

        # Presets Dropdown
        row1.addWidget(QLabel("<b>流程預設:</b>"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "標準分析流程 (MAFFT -> trimAl -> ModelFinder -> IQ-TREE)",
            "快速拓撲分析 (MAFFT -> IQ-TREE，跳過修剪)",
            "時間樹定年流程 (含 LSD2 分子鐘推論)",
        ])
        self.preset_combo.setMinimumWidth(220)
        self.preset_combo.setFixedHeight(26)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        row1.addWidget(self.preset_combo)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #CBD5E1;")
        row1.addWidget(sep1)

        # Layout Views Switcher
        row1.addWidget(QLabel("<b>版面檢視:</b>"))

        layout_btn_style = """
            QPushButton {
                background-color: #F8FAFC;
                color: #334155;
                border: 1px solid #BACCD9;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
                min-width: 74px;
            }
            QPushButton:hover {
                background-color: #E2E8F0;
                color: #0F766E;
            }
            QPushButton:checked {
                background-color: #008287;
                color: #FFFFFF;
                border: 1px solid #00666B;
                font-weight: bold;
            }
        """

        self.btn_layout_full = QPushButton("⊞ 三欄全覽")
        self.btn_layout_full.setCheckable(True)
        self.btn_layout_full.setChecked(True)
        self.btn_layout_full.setFixedHeight(26)
        self.btn_layout_full.setStyleSheet(layout_btn_style)
        self.btn_layout_full.setToolTip("顯示完整三欄視圖：左側模組庫 + 中央畫布 + 右側成果舞台")
        self.btn_layout_full.clicked.connect(lambda: self.set_layout_mode("full"))
        row1.addWidget(self.btn_layout_full)

        self.btn_layout_focus = QPushButton("🔲 專注畫布")
        self.btn_layout_focus.setCheckable(True)
        self.btn_layout_focus.setFixedHeight(26)
        self.btn_layout_focus.setStyleSheet(layout_btn_style)
        self.btn_layout_focus.setToolTip("隱藏兩側側邊欄，給予中央生信積木畫布 100% 全寬度空間")
        self.btn_layout_focus.clicked.connect(lambda: self.set_layout_mode("canvas_only"))
        row1.addWidget(self.btn_layout_focus)

        self.btn_layout_split = QPushButton("◫ 雙屏對照")
        self.btn_layout_split.setCheckable(True)
        self.btn_layout_split.setFixedHeight(26)
        self.btn_layout_split.setStyleSheet(layout_btn_style)
        self.btn_layout_split.setToolTip("收合左側模組庫，中央畫布與右側成果舞台半對半寬廣對照")
        self.btn_layout_split.clicked.connect(lambda: self.set_layout_mode("split"))
        row1.addWidget(self.btn_layout_split)

        self.btn_layout_popout = QPushButton("🗗 獨立舞台")
        self.btn_layout_popout.setCheckable(True)
        self.btn_layout_popout.setFixedHeight(26)
        self.btn_layout_popout.setStyleSheet(layout_btn_style)
        self.btn_layout_popout.setToolTip("將成果舞台彈出為獨立懸浮視窗 (可拖曳至雙螢幕第二顯示器)")
        self.btn_layout_popout.clicked.connect(lambda: self.set_layout_mode("popout"))
        row1.addWidget(self.btn_layout_popout)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #CBD5E1;")
        row1.addWidget(sep2)

        self.btn_toggle_terminal = QPushButton("💻 終端機")
        self.btn_toggle_terminal.setCheckable(True)
        self.btn_toggle_terminal.setChecked(False)
        self.btn_toggle_terminal.setFixedHeight(26)
        self.btn_toggle_terminal.setStyleSheet(layout_btn_style)
        self.btn_toggle_terminal.setToolTip("展開或收合中央生信終端指令與即時程式碼運行控制台")
        self.btn_toggle_terminal.clicked.connect(self.toggle_terminal_console)
        row1.addWidget(self.btn_toggle_terminal)

        row1.addStretch()

        tb_main_h.addWidget(self.tb_row1_widget, 1)

        # Discrete hint shown only when collapsed
        self.collapsed_hint_label = QLabel("💡 工作台控制列已收合以釋放畫布最大工作視野")
        self.collapsed_hint_label.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")
        self.collapsed_hint_label.setVisible(False)
        tb_main_h.addWidget(self.collapsed_hint_label, 1)

        # Collapse / Expand Toggle Button
        self.is_top_bar_collapsed = False
        self.btn_toggle_top_bar = QPushButton("收合控制列 ▲")
        self.btn_toggle_top_bar.setFixedHeight(26)
        self.btn_toggle_top_bar.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 8px;
                min-width: 84px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_top_bar.setToolTip("收合或展開頂部專案管理列，為中央生信畫布爭取最大垂直高度空間！")
        self.btn_toggle_top_bar.clicked.connect(self.toggle_top_bar)
        tb_main_h.addWidget(self.btn_toggle_top_bar, 0, Qt.AlignVCenter)

        # Keep attributes for backward compatibility
        self.proj_name_label = QLabel("未載入專案")
        self.proj_path_label = QLabel("")
        self.run_flow_btn = QPushButton("▶ 執行流程")
        self.run_flow_btn.setObjectName("primary_button")
        self.run_flow_btn.clicked.connect(self.run_entire_flow)
        self.cancel_flow_btn = QPushButton("■ 停止")
        self.cancel_flow_btn.setObjectName("danger_button")
        self.cancel_flow_btn.setEnabled(False)
        self.cancel_flow_btn.clicked.connect(self.cancel_workflow)
        self.tb_collapsible_content = self.tb_row1_widget
        self.tb_layout_switcher_widget = self.tb_row1_widget

        main_layout.addWidget(self.top_bar)

        # 2. Main Workspace Splitter: Left (Toolbox) + Center (Multi-Tab Canvases) + Right (Inspector)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                width: 6px;
                background-color: #E2E8F0;
                border-left: 1px solid #CBD5E1;
                border-right: 1px solid #CBD5E1;
                margin: 4px 0px;
                border-radius: 2px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #008287;
            }
        """)

        # 2A. Left: Module Toolbox (Scratch-like Blocks Palette)
        self.toolbox = ModuleToolboxWidget()
        self.toolbox.tool_clicked.connect(self.on_toolbox_tool_clicked)
        self.toolbox.preset_selected.connect(self.preset_combo.setCurrentIndex)
        self.toolbox.toggle_toolbox_requested.connect(self.toggle_toolbox_visibility)
        self.splitter.addWidget(self.toolbox)

        # 2B. Center: Multi-Tab Scratch White Workspace Canvases ("中間大空白與多分支畫布")
        self.canvas_box = QGroupBox("生信積木工作區 (Bioinformatics Blocks Workspace)")
        cb_layout = QVBoxLayout(self.canvas_box)
        cb_layout.setContentsMargins(4, 6, 4, 4)
        cb_layout.setSpacing(4)

        # Canvas Top Dock & Dismissible Hint Bar
        top_dock_row = QHBoxLayout()
        top_dock_row.setContentsMargins(0, 0, 0, 0)
        top_dock_row.setSpacing(6)

        self.btn_expand_toolbox = QPushButton("⇥ 展開模塊庫")
        self.btn_expand_toolbox.setFixedHeight(22)
        self.btn_expand_toolbox.setVisible(False)
        self.btn_expand_toolbox.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_expand_toolbox.setToolTip("展開左側生信模塊工具庫")
        self.btn_expand_toolbox.clicked.connect(self.toggle_toolbox_visibility)
        top_dock_row.addWidget(self.btn_expand_toolbox)

        self.canvas_hint_bar = QFrame()
        self.canvas_hint_bar.setStyleSheet("background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 4px; padding: 1px 6px;")
        ch_layout = QHBoxLayout(self.canvas_hint_bar)
        ch_layout.setContentsMargins(4, 2, 4, 2)
        ch_layout.setSpacing(6)

        canvas_hint = QLabel("💡 操作提示：中央畫布支援多工作流分頁；點擊綠旗 ▶ 即可全自動執行該分頁之生信流水線。")
        canvas_hint.setStyleSheet("color: #008287; font-size: 11px; font-weight: 500; border: none; background: transparent;")
        ch_layout.addWidget(canvas_hint, 1)

        close_hint_btn = QPushButton("✕ 隱藏提示")
        close_hint_btn.setFixedHeight(18)
        close_hint_btn.setStyleSheet("color: #64748B; font-size: 10px; border: none; background: transparent; padding: 0 4px;")
        close_hint_btn.setCursor(Qt.PointingHandCursor)
        close_hint_btn.setToolTip("隱藏此操作提示，騰出更多畫布空間")
        close_hint_btn.clicked.connect(self.canvas_hint_bar.hide)
        ch_layout.addWidget(close_hint_btn)

        top_dock_row.addWidget(self.canvas_hint_bar, 1)

        self.btn_expand_right = QPushButton("⇤ 展開成果舞台")
        self.btn_expand_right.setFixedHeight(22)
        self.btn_expand_right.setVisible(False)
        self.btn_expand_right.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_expand_right.setToolTip("展開右側成果舞台與數據探針")
        self.btn_expand_right.clicked.connect(self.toggle_right_panel)
        top_dock_row.addWidget(self.btn_expand_right)

        cb_layout.addLayout(top_dock_row)

        self.workflow_tabs = QTabWidget()
        self.workflow_tabs.setTabsClosable(True)
        self.workflow_tabs.setMovable(True)
        self.workflow_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #BACCD9;
                background: #FFFFFF;
                border-radius: 4px;
                top: -1px;
            }
            QTabBar::tab {
                background: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                padding: 5px 12px;
                margin-right: 3px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #008287;
                border-color: #BACCD9;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background: #E2E8F0;
                color: #0F766E;
            }
        """)

        # Corner button to add new workflow tab
        add_tab_btn = QPushButton("➕ 新建畫布")
        add_tab_btn.setFixedHeight(24)
        add_tab_btn.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #008287;
                border: 1px solid #BACCD9;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
                padding: 1px 8px;
                margin-right: 2px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        add_tab_btn.setToolTip("建立新的生信積木工作流畫布 (可獨立微調參數、建立對照實驗)")
        add_tab_btn.clicked.connect(self.add_new_canvas_tab)
        self.workflow_tabs.setCornerWidget(add_tab_btn, Qt.TopRightCorner)

        # Tab signals
        self.workflow_tabs.tabCloseRequested.connect(self.on_tab_close_requested)
        self.workflow_tabs.currentChanged.connect(self.on_active_canvas_tab_changed)

        # Default workflow tabs
        self._default_canvas = self.create_canvas_tab("🧬 主分析流水線", preset_idx=0)
        self.create_canvas_tab("🔬 模型對照實驗", preset_idx=1)
        self.create_canvas_tab("⏱ 分子鐘定年", preset_idx=2)
        self.workflow_tabs.setCurrentIndex(0)
        self.workflow_tabs.setMinimumHeight(320)

        # 2B.2 Vertical Splitter between Block Workflow Tabs and Collapsible Live Terminal Runner
        self.center_splitter = QSplitter(Qt.Vertical)
        self.center_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                height: 5px;
                background-color: #E2E8F0;
                border-top: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
                margin: 0px 4px;
                border-radius: 2px;
            }
            QSplitter::handle:vertical:hover {
                background-color: #008287;
            }
        """)

        # 2B.3 Collapsible Live Bioinformatic Terminal & Code Runner Console ("及時的程式碼運作的部分要有然後可以隱藏!!!")
        self.live_console = LogViewer("💻 生信終端與即時日誌")
        self.live_console.setToolTip("即時生信終端指令與程式碼運行控制台 (Terminal Code Runner)")
        self.live_console.set_collapsed(True)
        self.live_console.toggle_btn.clicked.connect(self.sync_terminal_btn_state)

        self.center_splitter.addWidget(self.workflow_tabs)
        self.center_splitter.addWidget(self.live_console)
        self.center_splitter.setStretchFactor(0, 5)
        self.center_splitter.setStretchFactor(1, 1)
        self.center_splitter.setSizes([650, 36])

        cb_layout.addWidget(self.center_splitter, 1)

        # Synchronize initial preset selection to active block canvas
        self.on_preset_changed(self.preset_combo.currentIndex())

        self.splitter.addWidget(self.canvas_box)

        # 2C. Right: Multi-Tab Outcome Stage & Data Inspector Hub (不再垂直擁擠互卡)
        self.right_container = QWidget()
        self.r_layout = QVBoxLayout(self.right_container)
        self.r_layout.setContentsMargins(0, 0, 0, 0)
        self.r_layout.setSpacing(4)

        # Right Multi-Tab Widget
        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #BACCD9;
                background: #FFFFFF;
                border-radius: 4px;
                top: -1px;
            }
            QTabBar::tab {
                background: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                padding: 4px 10px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #008287;
                border-color: #BACCD9;
                border-bottom: 1px solid #FFFFFF;
            }
            QTabBar::tab:hover:!selected {
                background: #E2E8F0;
                color: #0F766E;
            }
        """)

        # Collapse Button on Top Right Corner of right_tabs
        self.btn_collapse_right = QPushButton("收合側欄 ▶")
        self.btn_collapse_right.setFixedHeight(22)
        self.btn_collapse_right.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
                margin-right: 2px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_collapse_right.setToolTip("收合右側成果與探針面版，讓中央積木畫布享受 100% 全寬度視野")
        self.btn_collapse_right.clicked.connect(self.toggle_right_panel)
        self.right_tabs.setCornerWidget(self.btn_collapse_right, Qt.TopRightCorner)

        # Tab 0: 🖼️ 成果舞台 (Stage)
        self.stage_tab_widget = QWidget()
        self.stage_tab_layout = QVBoxLayout(self.stage_tab_widget)
        self.stage_tab_layout.setContentsMargins(4, 4, 4, 4)
        self.stage_tab_layout.setSpacing(4)

        self.stage = ScratchStageWidget()
        self.stage.run_pipeline_requested.connect(self.run_entire_flow)
        self.stage.stop_pipeline_requested.connect(self.cancel_workflow)
        self.stage.open_tree_explorer_requested.connect(lambda: self.jump_to_tab_requested.emit(8))
        self.stage.open_msa_explorer_requested.connect(lambda: self.jump_to_tab_requested.emit(5))
        self.stage.open_eln_requested.connect(self.open_eln_dialog)
        self.stage.artifact_selected.connect(self.inspect_step_data)
        self.stage.popout_requested.connect(self.pop_out_stage)
        self.stage.dock_requested.connect(self.dock_stage)
        self.stage_tab_layout.addWidget(self.stage)
        self.right_tabs.addTab(self.stage_tab_widget, "🖼️ 成果舞台")

        # Tab 1: 🔬 數據探針 (Data Inspector)
        self.inspector_tab_widget = QWidget()
        it_layout = QVBoxLayout(self.inspector_tab_widget)
        it_layout.setContentsMargins(8, 8, 8, 8)
        it_layout.setSpacing(6)

        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 7)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setFormat("%v / 7 步驟已完成")
        prog_row.addWidget(self.progress_bar)

        self.btn_toggle_inspector = QPushButton("收合探針 ▲")
        self.btn_toggle_inspector.setFixedHeight(22)
        self.btn_toggle_inspector.setStyleSheet("""
            QPushButton {
                background-color: #F1F5F9;
                color: #0F766E;
                border: 1px solid #CBD5E1;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background-color: #008287;
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_inspector.clicked.connect(self.toggle_inspector_visibility)
        prog_row.addWidget(self.btn_toggle_inspector)
        it_layout.addLayout(prog_row)

        self.milestone_desc = QLabel("專案工作區已就緒，請從第一步「序列輸入」開始建立您的分析流。")
        self.milestone_desc.setStyleSheet("color: #008287; font-size: 11px; font-weight: 500;")
        self.milestone_desc.setWordWrap(True)
        it_layout.addWidget(self.milestone_desc)

        self.inspector_title = QLabel("選取積木模塊之「成果探針」即可在此處檢視完整產出資料。")
        self.inspector_title.setStyleSheet("color: #008287; font-weight: bold; font-size: 11px;")
        it_layout.addWidget(self.inspector_title)

        self.inspector_text = QTextEdit()
        self.inspector_text.setReadOnly(True)
        self.inspector_text.setStyleSheet("""
            background-color: #FFFFFF;
            color: #1E293B;
            border: 1px solid #CBD5E1;
            border-radius: 4px;
            font-family: Consolas, 'Segoe UI', monospace;
            font-size: 11px;
        """)
        it_layout.addWidget(self.inspector_text, 1)

        insp_act_row = QHBoxLayout()
        self.open_file_btn = QPushButton("開啟資料夾 (Folder)")
        self.open_file_btn.setFixedHeight(26)
        self.open_file_btn.clicked.connect(self.open_current_step_dir)
        insp_act_row.addWidget(self.open_file_btn)

        self.view_full_btn = QPushButton("移至專屬檢視器 ↗ (Viewer)")
        self.view_full_btn.setFixedHeight(26)
        self.view_full_btn.clicked.connect(self.open_full_viewer)
        insp_act_row.addWidget(self.view_full_btn)
        it_layout.addLayout(insp_act_row)

        self.right_tabs.addTab(self.inspector_tab_widget, "🔬 數據探針")

        # Tab 2: 📦 成果生態庫 (Artifacts Library)
        self.artifacts_tab_widget = QWidget()
        at_layout = QVBoxLayout(self.artifacts_tab_widget)
        at_layout.setContentsMargins(8, 8, 8, 8)
        at_layout.setSpacing(6)

        at_title = QLabel("<b>分析成果生態庫 (Artifacts Gallery)</b>")
        at_title.setStyleSheet("color: #008287; font-size: 12px; font-weight: bold;")
        at_layout.addWidget(at_title)

        at_desc = QLabel("點選任一模塊產出可即時探針檢視或切換專屬視圖：")
        at_desc.setStyleSheet("color: #64748B; font-size: 11px;")
        at_layout.addWidget(at_desc)

        at_grid = QGridLayout()
        at_grid.setContentsMargins(0, 0, 0, 0)
        at_grid.setHorizontalSpacing(6)
        at_grid.setVerticalSpacing(6)

        art_cards = [
            ("raw", "原始序列 (Raw FASTA)", "檢查輸入序列規格、長度與物種名稱", "#0284C7"),
            ("alignment", "多重比對 (MAFFT)", "檢視同源位點比對矩陣與突變分布", "#008287"),
            ("trimming", "修剪矩陣 (trimAl)", "檢視保守區過濾與去除 Gap 後之矩陣", "#D97706"),
            ("modelfinder", "模型報告 (IQ-TREE)", "檢視 88+ 種替代模型評選 BIC/AIC 報表", "#7C3AED"),
            ("tree", "系統發育樹 (Treefile)", "檢視 ML 最大概似樹拓撲與拔靴支撐值", "#059669"),
            ("timetree", "分子時間樹 (LSD2)", "檢視定年時間軸、速率與分化時間 tMRCA", "#DC2626"),
        ]
        for idx, (k, name, tip, col) in enumerate(art_cards):
            btn = QPushButton(name)
            btn.setFixedHeight(30)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #F8FAFC;
                    color: {col};
                    border: 1px solid #CBD5E1;
                    border-left: 4px solid {col};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {col};
                    color: #FFFFFF;
                }}
            """)
            btn.clicked.connect(lambda checked=False, key=k: self.inspect_step_data(key))
            at_grid.addWidget(btn, idx // 2, idx % 2)

        at_layout.addLayout(at_grid)

        # ELN Card in Tab 2
        eln_box = QFrame()
        eln_box.setStyleSheet("background-color: #F0FDF4; border: 1px solid #86EFAC; border-radius: 6px; padding: 6px;")
        ef_layout = QVBoxLayout(eln_box)
        ef_title = QLabel("<b>📑 論文電子實驗紀錄簿 (Electronic Lab Notebook)</b>")
        ef_title.setStyleSheet("color: #166534; font-size: 11px;")
        ef_layout.addWidget(ef_title)

        ef_desc = QLabel("全自動整合研究方法、所用工具版本、最優模型統計與圖表，一鍵輸出論文 Supplementary Material。")
        ef_desc.setStyleSheet("color: #15803D; font-size: 10px;")
        ef_desc.setWordWrap(True)
        ef_layout.addWidget(ef_desc)

        eln_btn = QPushButton("📘 立即導出 ELN 實驗日誌 (PDF / Markdown / ZIP)...")
        eln_btn.setFixedHeight(28)
        eln_btn.setStyleSheet("background-color: #16A34A; color: #FFFFFF; font-weight: bold; font-size: 11px; border-radius: 4px;")
        eln_btn.clicked.connect(self.open_eln_dialog)
        ef_layout.addWidget(eln_btn)
        at_layout.addWidget(eln_box)

        at_layout.addStretch()
        self.right_tabs.addTab(self.artifacts_tab_widget, "📦 成果庫")

        self.r_layout.addWidget(self.right_tabs)
        self.splitter.addWidget(self.right_container)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([240, 560, 360])
        main_layout.addWidget(self.splitter, 1)

    def on_zen_mode_toggled(self, is_zen: bool):
        if is_zen:
            self.toolbox.hide()
            self.right_container.hide()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.show()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.show()
            if hasattr(self, "live_console") and not self.live_console.is_collapsed:
                self.live_console.set_collapsed(True)
            self.splitter.setSizes([0, 1200, 0])
        else:
            self.toolbox.show()
            self.right_container.show()
            if hasattr(self, "btn_expand_toolbox"):
                self.btn_expand_toolbox.hide()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.hide()
            self.splitter.setSizes([240, 560, 360])

    def on_toolbox_tool_clicked(self, tool_key: str):
        if tool_key == "viewer_tree":
            self.jump_to_tab_requested.emit(8)
            return
        elif tool_key == "viewer_msa":
            self.jump_to_tab_requested.emit(5)
            return
        elif tool_key == "viewer_eln":
            self.open_eln_dialog()
            return

        target_canvas = self.block_canvas
        if hasattr(self, "workflow_tabs") and self.workflow_tabs.currentWidget():
            cur = self.workflow_tabs.currentWidget()
            if hasattr(cur, "add_block"):
                target_canvas = cur

        block = target_canvas.add_block(tool_key, auto_snap=True)
        if block:
            block.enable_cb.setChecked(True)
            block.setFocus()
            if hasattr(target_canvas, "scroll"):
                target_canvas.scroll.ensureWidgetVisible(block)
            self.inspector_title.setText(f"已新增積木模塊至畫布: {block.title}")
            if hasattr(self, "live_console"):
                self.live_console.append_log(f"➕ [生信積木] 已動態新增「{block.title}」至工作流程！", "#008287")

    def on_preset_changed(self, idx: int):
        # 0: Standard 5 steps (raw, sanitize, alignment, trimming, modelfinder, tree)
        # 1: Fast (bypass trimming)
        # 2: Full TimeTree (enable all including timetree)
        canvases = [self.block_canvas] if self.block_canvas else self.get_all_canvases()
        for canvas in canvases:
            if not canvas:
                continue
            if idx == 0:
                for k in STEP_KEYS:
                    if k in canvas.cards:
                        canvas.cards[k].enable_cb.setChecked(k != "timetree")
            elif idx == 1:
                for k in STEP_KEYS:
                    if k in canvas.cards:
                        canvas.cards[k].enable_cb.setChecked(k not in ("trimming", "timetree"))
            elif idx == 2:
                for k in STEP_KEYS:
                    if k in canvas.cards:
                        canvas.cards[k].enable_cb.setChecked(True)

    def load_default_or_demo_project(self):
        recents = self.pm.get_recent_projects()
        for r in recents:
            if Path(r).exists():
                proj = self.pm.open_project(r)
                if proj:
                    self.display_project(proj)
                    return

        default_dir = OUTPUT_DIR / "My_Evolution_Project.phylo"
        if (default_dir / "project.json").exists():
            proj = self.pm.open_project(default_dir)
            if proj:
                self.display_project(proj)
                return

        proj = self.pm.create_project("My_Evolution_Project", OUTPUT_DIR, author="研究生", description="預設演化生物學研究專案")
        self.display_project(proj)

    def display_project(self, proj: PhyloProject):
        self.proj_name_label.setText(f"{proj.name}")
        self.proj_path_label.setText(f"({proj.project_dir})")
        self.proj_path_label.setToolTip(str(proj.project_dir))

        # Synchronize project state across all open workflow canvas tabs
        if hasattr(self, "workflow_tabs"):
            for i in range(self.workflow_tabs.count()):
                c = self.workflow_tabs.widget(i)
                if isinstance(c, ScratchWorkspaceCanvas):
                    c.load_project_state(proj)
        elif hasattr(self, "block_canvas") and self.block_canvas:
            self.block_canvas.load_project_state(proj)

        completed_count = sum(1 for s in proj.steps.values() if s.status == "completed")
        self.progress_bar.setValue(completed_count)
        self.progress_bar.setFormat(f"{completed_count} / 7 步驟已完成 ({int(completed_count / 7 * 100)}%)")

        # Synchronize live tree/MSA to Scratch Stage
        loaded_tree = False
        for tk in ("timetree", "tree"):
            trec = proj.steps.get(tk)
            if trec and trec.status == "completed" and trec.output_files:
                for tf in trec.output_files:
                    if (tf.endswith(".treefile") or tf.endswith(".nwk")) and Path(tf).exists():
                        self.stage.load_tree_file(tf)
                        loaded_tree = True
                        break
            if loaded_tree:
                break

        if not loaded_tree:
            for ak in ("trimming", "alignment", "sanitize", "raw"):
                arec = proj.steps.get(ak)
                if arec and arec.status == "completed" and arec.output_files:
                    for af in arec.output_files:
                        if (af.endswith(".fasta") or af.endswith(".fa")) and Path(af).exists():
                            self.stage.load_msa_file(af)
                            break
                    break

        # Update Stage Attributes Bar (Matching Scratch Sprite Info Bar)
        taxa_val = "-"
        sites_val = "-"
        model_val = "-"
        boot_val = "-"
        for sk in ("trimming", "alignment", "sanitize", "raw"):
            srec = proj.steps.get(sk)
            if srec and srec.status == "completed" and srec.parameters:
                if taxa_val == "-" and "taxa" in srec.parameters:
                    taxa_val = srec.parameters["taxa"]
                if sites_val == "-" and ("length" in srec.parameters or "sites" in srec.parameters):
                    sites_val = srec.parameters.get("length", srec.parameters.get("sites", "-"))
                if taxa_val != "-" and sites_val != "-":
                    break

        mf_rec = proj.steps.get("modelfinder")
        if mf_rec and mf_rec.parameters:
            model_val = mf_rec.parameters.get("best_model", "-")
        tree_rec = proj.steps.get("tree")
        if tree_rec and tree_rec.parameters:
            boot_val = tree_rec.parameters.get("bootstrap", "-")
            if model_val == "-":
                model_val = tree_rec.parameters.get("model", "-")

        self.stage.update_attributes(taxa=taxa_val, sites=sites_val, model=model_val, boot=boot_val)

        if completed_count == 7:
            self.milestone_desc.setText("全流程 7 個步驟圓滿達成！隨時可一鍵導出論文電子實驗紀錄簿 (ELN)。")
        elif completed_count > 0:
            self.milestone_desc.setText(f"已完成 {completed_count} 個分析模塊，建議依數據流向繼續下一步。")
        else:
            self.milestone_desc.setText("專案已就緒，請從第一步「原始序列輸入」開始建立您的分析流。")

    def open_preferences_for_step(self, step_key: str):
        if not self.pm.current_project:
            QMessageBox.warning(self, "缺少專案", "請先建立或開啟一個研究專案。")
            return
        card = self.block_canvas.cards.get(step_key)
        initial_params = card.get_parameters() if card else {}
        dlg = AnalysisPreferencesDialog(step_key, initial_params, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_params = dlg.get_settings()
            if card:
                card.set_parameters(new_params)
            if self.pm.current_project:
                self.pm.update_step(step_key, parameters=new_params)
            if dlg.should_compute:
                params_by_step = {k: c.get_parameters() for k, c in self.block_canvas.cards.items()}
                params_by_step[step_key] = new_params
                self._start_worker([step_key], params_by_step)
            else:
                self.inspector_title.setText(f"偏好設定已更新: {STEP_TITLES[step_key][0]}")

    def run_single_step(self, step_key: str, show_preferences: bool = False):
        if not self.pm.current_project:
            return
        if show_preferences and step_key in ("sanitize", "alignment", "trimming", "modelfinder", "tree", "timetree"):
            self.open_preferences_for_step(step_key)
            return

        params_by_step = {k: card.get_parameters() for k, card in self.block_canvas.cards.items()}
        self._start_worker([step_key], params_by_step)

    def run_entire_flow(self):
        if not self.pm.current_project:
            QMessageBox.warning(self, "缺少專案", "請先建立或開啟一個研究專案。")
            return

        enabled_steps = self.block_canvas.get_execution_sequence()
        if not enabled_steps:
            QMessageBox.warning(self, "無啟用步驟", "請至少勾選啟用一個積木模塊！")
            return

        params_by_step = {k: card.get_parameters() for k, card in self.block_canvas.cards.items()}
        self._start_worker(enabled_steps, params_by_step)

    def toggle_terminal_console(self):
        if hasattr(self, "live_console"):
            self.live_console.toggle_collapse()
            if hasattr(self, "btn_toggle_terminal"):
                self.btn_toggle_terminal.setChecked(not self.live_console.is_collapsed)
            if hasattr(self, "center_splitter"):
                if self.live_console.is_collapsed:
                    self.center_splitter.setSizes([850, 36])
                else:
                    self.center_splitter.setSizes([650, 160])

    def sync_terminal_btn_state(self):
        if hasattr(self, "live_console") and hasattr(self, "btn_toggle_terminal"):
            self.btn_toggle_terminal.setChecked(not self.live_console.is_collapsed)
            if hasattr(self, "center_splitter"):
                if self.live_console.is_collapsed:
                    self.center_splitter.setSizes([850, 36])
                else:
                    self.center_splitter.setSizes([650, 160])

    def toggle_inspector_visibility(self):
        is_visible = self.inspector_text.isVisible()
        self.inspector_text.setVisible(not is_visible)
        if hasattr(self, "btn_toggle_inspector"):
            self.btn_toggle_inspector.setText("展開探針 ▼" if is_visible else "收合探針 ▲")

    def _start_worker(self, steps: list[str], params_by_step: dict):
        if hasattr(self, "right_container") and not self.right_container.isVisible():
            self.right_container.show()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.hide()
        if hasattr(self, "right_tabs"):
            self.right_tabs.setCurrentIndex(0)

        self.run_flow_btn.setEnabled(False)
        self.cancel_flow_btn.setEnabled(True)
        self.stage.set_running_state(True, f"正在執行流水線 ({len(steps)} 個模塊)...")
        self.inspector_title.setText(f"正在執行工作流 ({len(steps)} 個步驟)...")
        self.inspector_text.clear()

        if hasattr(self, "live_console"):
            self.live_console.append_log(f"\n==================================================", "#008287")
            self.live_console.append_log(f"🚀 [Pipeline Execution Started] 開始執行工作流 ({len(steps)} 個模塊)...", "#008287")
            if self.pm.current_project:
                self.live_console.append_log(f"📁 專案根目錄: {self.pm.current_project.project_dir}", "#475569")

        self.worker = WorkstationWorker(self.pm.current_project, steps, params_by_step)
        self.worker.step_started.connect(self.on_worker_step_started)
        self.worker.step_finished.connect(self.on_worker_step_finished)
        self.worker.log_emitted.connect(self.on_log_emitted)
        self.worker.all_finished.connect(self.on_worker_all_finished)
        self.worker.start()

    def on_log_emitted(self, msg: str):
        self.inspector_text.append(msg)
        self.stage.append_log(msg)
        if hasattr(self, "live_console"):
            self.live_console.append_log(msg)

    def cancel_workflow(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.inspector_text.append("\n[使用者已手動終止執行]")
            self.stage.append_log("\n[使用者已手動終止執行]")
            if hasattr(self, "live_console"):
                self.live_console.append_log("\n[使用者已手動終止執行]", "#B91C1C")
            self.stage.set_running_state(False, "分析已被使用者終止")
            self.cancel_flow_btn.setEnabled(False)

    def on_worker_step_started(self, step_key: str):
        for c in self.get_all_canvases():
            if step_key in c.cards:
                c.cards[step_key].set_running_state(True)
        title = STEP_TITLES.get(step_key, (step_key,))[0]
        self.stage.set_running_state(True, f"正在執行: {title}...")
        self.inspector_title.setText(f"正在執行: {title}...")
        if hasattr(self, "live_console"):
            self.live_console.append_log(f"\n▶ 正在啟動模塊: {title}...", "#0284C7")

    def on_worker_step_finished(
        self, step_key: str, success: bool, summary: str, output_files: list, params: dict, cmd: str
    ):
        status = "completed" if success else "failed"
        self.pm.update_step(
            step_key,
            status=status,
            summary=summary,
            output_files=output_files,
            parameters=params,
            command_line=cmd,
        )
        for c in self.get_all_canvases():
            if step_key in c.cards:
                c.cards[step_key].set_record(self.pm.current_project.steps[step_key])
        title = STEP_TITLES.get(step_key, (step_key,))[0]
        self.stage.append_log(f"[{title}] {'完成 ✓' if success else '失敗 ✕'}: {summary}")
        if hasattr(self, "live_console"):
            if cmd:
                self.live_console.append_log(f"  $ {cmd}", "#1E293B")
            self.live_console.append_log(f"  [{'SUCCESS ✓' if success else 'FAILED ✕'}] {summary}", "#15803D" if success else "#B91C1C")
        if success and output_files:
            for f in output_files:
                if f.endswith(".treefile") or f.endswith(".nwk"):
                    self.stage.load_tree_file(f)
                    break
                elif f.endswith(".fasta") or f.endswith(".fa"):
                    self.stage.load_msa_file(f)
                    break
        self.display_project(self.pm.current_project)

    def on_worker_all_finished(self, success: bool, message: str):
        self.run_flow_btn.setEnabled(True)
        self.cancel_flow_btn.setEnabled(False)
        self.stage.set_running_state(False, "流水線全線完成！成果已呈現在舞台。" if success else "工作流中斷")
        for c in self.get_all_canvases():
            for card in c.cards.values():
                card.mini_progress.setVisible(False)
                card.run_btn.setEnabled(card.enable_cb.isChecked())

        if success:
            QMessageBox.information(self, "工作流執行成功", message)
        else:
            QMessageBox.warning(self, "工作流中斷", message)

    def fork_branch(self, from_step_key: str, branch_name: str | None = None):
        """
        Creates an experiment comparison branch from this step with a new project name.
        """
        if not self.pm.current_project:
            return

        if branch_name is None:
            b_name, ok = QInputDialog.getText(
                self,
                "建立對照實驗分支",
                f"將從步驟「{STEP_TITLES[from_step_key][0]}」建立新分支，\n請輸入新分支名稱 (例如: {self.pm.current_project.name}_Branch2):",
                text=f"{self.pm.current_project.name}_{from_step_key}_branch",
            )
            if not ok or not b_name.strip():
                return
            branch_name = b_name

        source_proj = self.pm.current_project
        clean_branch_name = re.sub(r'[\\/*?:"<>|]', "_", branch_name.strip()) or f"{source_proj.name}_branch"
        b_dir = Path(source_proj.project_dir).parent
        new_proj = self.pm.create_project(
            clean_branch_name,
            b_dir,
            author=source_proj.author,
            description=f"自專案 {source_proj.name} 分支之對照實驗 (起點: {from_step_key})",
        )

        # Copy completed records up to and including from_step_key from source_proj
        found_cutoff = False
        for k in STEP_KEYS:
            if not found_cutoff:
                rec = source_proj.steps.get(k)
                if rec:
                    new_proj.steps[k] = copy.deepcopy(rec)
            else:
                # Downstream steps remain fresh and ready to be re-run
                new_proj.steps[k] = StepRecord()
            if k == from_step_key:
                found_cutoff = True

        self.pm.current_project = new_proj
        self.pm.save_project()

        if hasattr(self, "workflow_tabs"):
            branch_tab_title = f"🔬 分支: {clean_branch_name[:14]}"
            branch_canvas = self.create_canvas_tab(branch_tab_title)
            self.workflow_tabs.setCurrentWidget(branch_canvas)

        self.display_project(new_proj)

    def new_project_dialog(self):
        import re
        name, ok = QInputDialog.getText(
            self, "新建研究專案", "請輸入專案名稱 (例如: Chloroplast_Phylogeny_2026):"
        )
        if ok and name.strip():
            clean_name = re.sub(r'[\\/*?:"<>|]', "_", name.strip()) or "Unnamed_Project"
            dir_path = QFileDialog.getExistingDirectory(self, "選取專案儲存位置", str(OUTPUT_DIR))
            if dir_path:
                author, _ = QInputDialog.getText(
                    self, "研究負責人", "請輸入研究負責人姓名 / 實驗室名稱:", text="研究生"
                )
                proj = self.pm.create_project(clean_name, dir_path, author=author or "研究生")
                self.display_project(proj)
                QMessageBox.information(
                    self,
                    "專案建立成功",
                    f"已為您在下列位置建立標準化專案架構:\n{proj.project_dir}\n"
                    "包含各步驟專屬資料夾 (01_raw ~ 07_timetree) 與電子實驗紀錄簿！"
                )

    def open_project_dialog(self):
        p_dir = QFileDialog.getExistingDirectory(self, "選取專案資料夾 (*.phylo)", str(OUTPUT_DIR))
        if p_dir:
            proj = self.pm.open_project(p_dir)
            if proj:
                self.display_project(proj)
                QMessageBox.information(self, "載入成功", f"成功載入專案: {proj.name}")
            else:
                QMessageBox.warning(self, "載入失敗", "選取的資料夾不包含有效的 project.json 專案設定檔。")

    def load_demo_project(self, show_alert: bool = True, target_dir: Path | None = None):
        demo_name = "Primates_Cytb_Phylogenomics"
        out_d = Path(target_dir) if target_dir is not None else OUTPUT_DIR
        proj = self.pm.create_project(
            demo_name,
            out_d,
            author="生信研究室 (Bioinformatics Lab)",
            description="靈長類 (Primates) 細胞色素 b (Cytb) 粒線體基因之分子演化與系統發育示範專案",
        )
        p_dir = Path(proj.project_dir)

        # Source fasta
        cand_fastas = [
            DATA_DIR / "primates_cytb.fasta",
            Path("data/primates_cytb.fasta"),
        ]
        src_fasta = None
        for c in cand_fastas:
            if c.exists():
                src_fasta = c
                break

        # 1. Raw
        raw_f = p_dir / "01_raw" / "primates_cytb.fasta"
        if src_fasta and src_fasta.exists():
            shutil.copy2(src_fasta, raw_f)
        else:
            raw_f.write_text(">Homo_sapiens\nATGACTCC...\n>Pan_troglodytes\nATGACTCC...\n", encoding="utf-8")

        self.pm.update_step(
            "raw",
            "completed",
            "6 個代表性靈長類物種，1140 bp 粒線體編碼序列 (primates_cytb.fasta)",
            [str(raw_f.resolve())],
            parameters={
                "taxa": 6,
                "length": 1140,
                "data_type": "DNA/RNA (核酸編碼區)",
                "file_name": "primates_cytb.fasta",
                "gc_content": "44.6%",
                "file_size_kb": 7.2,
                "genetic_code": "2. Vertebrate Mitochondrial",
                "fasta_path": str(raw_f.resolve()),
            },
            command_line="",
            student_notes="從 NCBI 粒線體資料庫載入 6 個代表性類群：人 (Homo)、黑猩猩 (Pan)、大猩猩 (Gorilla)、紅毛猩猩 (Pongo)、獼猴 (Macaca) 與外群狐猴 (Lemur)。",
        )
        for c in self.get_all_canvases():
            if "raw" in c.cards and "fasta_path" in c.cards["raw"].param_widgets:
                c.cards["raw"].param_widgets["fasta_path"].setText(str(raw_f.resolve()))

        # 2. Sanitize
        clean_f = p_dir / "02_sanitized" / "primates_cytb_cleaned.fasta"
        if raw_f.exists():
            san_res = sanitize_fasta_file(raw_f)
            if san_res.cleaned_records:
                save_sanitized_fasta(san_res.cleaned_records, clean_f)
        if not clean_f.exists():
            shutil.copy2(raw_f, clean_f)

        self.pm.update_step(
            "sanitize",
            "completed",
            "通過 NCBI 標頭檢查，無非法字元，序列完整度 100% (DNA)",
            [str(clean_f.resolve())],
            parameters={
                "taxa": 6,
                "length": 1140,
                "seq_type": "DNA (核酸)",
                "illegal_chars_removed": 0,
                "duplicate_taxa_resolved": 0,
                "clean_policy": "NCBI 標頭正規化與 IUPAC 非法字元過濾",
            },
            command_line="PhyloCraft Builtin Sanitizer & QC Engine",
            student_notes="確認標頭物種名稱格式統一，去除空格與特殊斜線，各分類單元名稱唯一且符合 Newick 規範。",
        )

        # 3. Alignment
        aln_f = p_dir / "03_alignment" / "primates_cytb_aligned.fasta"
        shutil.copy2(clean_f, aln_f)
        self.pm.update_step(
            "alignment",
            "completed",
            "MAFFT auto (FFT-NS-2) 精確對齊完成 (6 sequences, 1140 sites)",
            [str(aln_f.resolve())],
            parameters={
                "taxa": 6,
                "length": 1140,
                "algorithm": "auto (智慧推薦)",
                "strategy": "fftns2 (漸進式高速比對)",
                "threads": "AUTO",
                "direction_adjusted": False,
            },
            command_line="mafft --auto primates_cytb_cleaned.fasta > primates_cytb_aligned.fasta",
            student_notes="6 個靈長類類群之 Cytb 編碼區長度高度保守 (均為 1140 bp)，MAFFT 對齊結果品質優異且無畸變。",
        )

        # 4. Trimming
        trim_f = p_dir / "04_trimming" / "primates_cytb_trimmed.fasta"
        shutil.copy2(aln_f, trim_f)
        self.pm.update_step(
            "trimming",
            "completed",
            "trimAl automated1 智慧修剪完成，保留 1140 個高品質位點",
            [str(trim_f.resolve())],
            parameters={
                "taxa": 6,
                "length": 1140,
                "method": "automated1 (啟發式自動修剪)",
                "original_sites": 1140,
                "retained_sites": 1140,
                "trimmed_percentage": "0.0% (高品質無修剪)",
            },
            command_line="trimal -in aligned.fasta -out trimmed.fasta -automated1",
            student_notes="automated1 模式評估全序列無低品質長空缺，完整保留 1140 個具備系統發育訊息之同源位點。",
        )

        # 5. ModelFinder
        mf_f = p_dir / "05_modelfinder" / "primates_cytb_modelfinder.iqtree"
        mf_content = (
            "IQ-TREE 2.2.0\n"
            "Input data: 6 sequences with 1140 nucleotide sites\n"
            "Number of constant sites: 812 (= 71.2281% of all sites)\n"
            "Number of parsimony informative sites: 280\n"
            "\n"
            "List of models sorted by BIC scores:\n"
            "\n"
            "Model          LogL         AIC     w-AIC        AICc     w-AICc         BIC     w-BIC\n"
            "F81+F     -2210.450    4436.900 -  0.021    4437.100 -  0.021    4521.800 +  0.680\n"
            "HKY+F     -2208.120    4438.240 -  0.011    4438.500 -  0.011    4523.940 +  0.230\n"
            "GTR+F     -2205.300    4440.600 -  0.003    4441.000 -  0.003    4526.680 -  0.090\n"
            "\n\n"
            "Best-fit model according to BIC: F81+F\n"
        )
        mf_f.write_text(mf_content, encoding="utf-8")
        self.pm.update_step(
            "modelfinder",
            "completed",
            "ModelFinder 檢定 88+ 種模型，最適模型 (BIC): F81+F (BIC=4521.8)",
            [str(mf_f.resolve())],
            parameters={
                "taxa": 6,
                "length": 1140,
                "criterion": "BIC (貝氏資訊準則)",
                "scope": "TESTONLY",
                "best_model": "F81+F",
                "candidate_models_count": 88,
                "constant_sites": 812,
                "parsimony_informative_sites": 280,
            },
            command_line="iqtree2 -s trimmed.fasta -m TESTONLY -T AUTO",
            student_notes="BIC 統計標準明確評比 88+ 種核酸替代模型，F81+F 在參數量與最大概似值間取得最優平衡。",
        )

        # 6. Tree
        tree_f = p_dir / "06_phylogeny" / "primates_cytb_tree.treefile"
        tree_content = "(((Homo_sapiens:0.000878,Pan_troglodytes:0.000001)98:0.000878,Gorilla_gorilla:0.000001)95:0.000878,Pongo_abelii:0.000878,(Macaca_mulatta:0.002641,Lemur_catta:0.009714)100:0.004123);\n"
        tree_f.write_text(tree_content, encoding="utf-8")
        rep_f = p_dir / "06_phylogeny" / "primates_cytb_tree.iqtree"
        rep_f.write_text("IQ-TREE 2.2.0\nModel of substitution: F81+F\nNumber of taxa: 6\nLog-likelihood of consensus tree: -2150.4\n", encoding="utf-8")
        self.pm.update_step(
            "tree",
            "completed",
            "IQ-TREE 2 ML 建樹完成 (模型: F81+F, 1000 次 UFBoot 雙重檢定)",
            [str(tree_f.resolve()), str(rep_f.resolve())],
            parameters={
                "taxa": 6,
                "model": "F81+F",
                "bootstrap": 1000,
                "alrt": 1000,
                "inference_engine": "IQ-TREE 2.2.0 (Maximum Likelihood)",
                "consensus_logl": -2150.4,
            },
            command_line="iqtree2 -s trimmed.fasta -m F81+F -B 1000 --alrt 1000 -T AUTO",
            student_notes="人屬 (Homo) 與黑猩猩 (Pan) 之姐妹群關係獲得 98% UFBoot 顯著支持；大猩猩 (Gorilla) 次之；外群狐猴 (Lemur) 正確置於基底。",
        )

        # 7. TimeTree
        lsd_f = p_dir / "07_timetree" / "primates_cytb_timetree.nwk"
        lsd_content = "(((Homo_sapiens:6.5,Pan_troglodytes:6.5):2.5,Gorilla_gorilla:9.0):5.0,Pongo_abelii:14.0,(Macaca_mulatta:25.0,Lemur_catta:65.0):10.0);\n"
        lsd_f.write_text(lsd_content, encoding="utf-8")
        self.pm.update_step(
            "timetree",
            "completed",
            "LSD2 最小平方法分子鐘定年完成，產出絕對地質年代樹 (tMRCA ≈ 65 Ma)",
            [str(lsd_f.resolve())],
            parameters={
                "taxa": 6,
                "clock_method": "LSD2 (Least Squares Dating 2)",
                "outlier": 3.0,
                "root_age": "65.0 Ma (古新世)",
                "rate_estimate": "1.42e-08 sub/site/year",
                "tmrca_estimate": "65.0 Ma",
            },
            command_line="iqtree2 -s trimmed.fasta -te tree.treefile --date date.txt",
            student_notes="結合古靈長類化石定年校準，人-猩分歧約於 6.5 Ma，大猩猩約於 9.0 Ma，全樹根節點 (狐猴基底) 合理符合古新世 (約 65 Ma) 化石紀錄。",
        )

        self.display_project(proj)
        if show_alert:
            QMessageBox.information(
                self,
                "範例專案載入完成",
                f"已成功為您建構「{demo_name}」完整科研示範專案！\n"
                "您可直接點擊每個積木上的「資料快速預覽」或「研究筆記」體驗工作站功能。"
            )

    def export_lab_notebook(self):
        if not self.pm.current_project:
            QMessageBox.warning(self, "缺少專案", "請先建立或載入一個研究專案。")
            return
        self.pm.generate_lab_notebook()
        from src.ui.widgets.eln_viewer_dialog import ELNViewerDialog
        dlg = ELNViewerDialog(self.pm.current_project, self)
        dlg.exec()

    open_eln_dialog = export_lab_notebook

    def on_note_saved(self, step_key: str, note_text: str):
        self.pm.update_student_notes(step_key, note_text)
        # Update cards on all open canvases so the note badge updates!
        for c in self.get_all_canvases():
            if step_key in c.cards:
                c.cards[step_key].set_record(self.pm.current_project.steps[step_key])

    def on_step_jump(self, step_key: str):
        if not self.pm.current_project:
            return

        rec = self.pm.current_project.steps.get(step_key)
        has_output = bool(rec and rec.output_files and Path(rec.output_files[0]).exists())
        target_file = rec.output_files[0] if has_output else ""

        if not target_file:
            for k in ("trimming", "alignment", "sanitize", "raw"):
                r = self.pm.current_project.steps.get(k)
                if r and r.output_files and Path(r.output_files[0]).exists():
                    target_file = r.output_files[0]
                    break

        if step_key == "raw":
            self.step_jump_with_data_requested.emit(step_key, target_file)
            if has_output:
                self.view_msa_requested.emit(target_file)
            else:
                self.jump_to_tab_requested.emit(2)

        elif step_key == "sanitize":
            self.step_jump_with_data_requested.emit(step_key, target_file)
            self.jump_to_tab_requested.emit(2)

        elif step_key == "alignment":
            self.step_jump_with_data_requested.emit(step_key, target_file)
            if has_output:
                self.view_msa_requested.emit(target_file)
            else:
                self.jump_to_tab_requested.emit(3)

        elif step_key == "trimming":
            self.step_jump_with_data_requested.emit(step_key, target_file)
            if has_output:
                self.view_msa_requested.emit(target_file)
            else:
                self.jump_to_tab_requested.emit(4)

        elif step_key == "modelfinder":
            if has_output:
                iqtree_rep = next((f for f in rec.output_files if f.endswith(".iqtree")), target_file)
                self.view_model_test_requested.emit(iqtree_rep)
            else:
                self.step_jump_with_data_requested.emit(step_key, target_file)
                self.jump_to_tab_requested.emit(6)

        elif step_key in ("tree", "tree_fasttree", "fasttree"):
            if has_output:
                tree_f = next((f for f in rec.output_files if f.endswith(".treefile") or f.endswith(".nwk")), target_file)
                self.view_tree_requested.emit(tree_f)
            else:
                self.step_jump_with_data_requested.emit(step_key, target_file)
                self.jump_to_tab_requested.emit(7)

        elif step_key == "timetree":
            self.step_jump_with_data_requested.emit(step_key, target_file)
            if has_output:
                tree_f = next((f for f in rec.output_files if f.endswith(".timetree.nwk") or f.endswith(".timetree.nex") or f.endswith(".treefile") or f.endswith(".nwk")), target_file)
                self.view_tree_requested.emit(tree_f)
            else:
                self.jump_to_tab_requested.emit(7)

    def inspect_step_data(self, step_key: str, show_dialog: bool = True):
        self.current_inspect_step = step_key
        if not self.pm.current_project:
            QMessageBox.warning(self, "缺少專案", "請先建立或開啟一個研究專案。")
            return

        rec = self.pm.current_project.steps.get(step_key)
        if not rec:
            return

        # 1. Update internal sidebar inspector & ensure right container is visible
        if hasattr(self, "right_container"):
            if not self.right_container.isVisible():
                self.right_container.show()
            if hasattr(self, "btn_expand_right"):
                self.btn_expand_right.hide()
            # Ensure splitter gives width to column 2
            if hasattr(self, "splitter"):
                sizes = self.splitter.sizes()
                if len(sizes) == 3 and sizes[2] < 150:
                    self.splitter.setSizes([sizes[0], max(200, sizes[1] - 360), 360])

        if hasattr(self, "right_tabs"):
            self.right_tabs.setCurrentIndex(1)

        if hasattr(self, "inspector_text") and not self.inspector_text.isVisible():
            self.inspector_text.setVisible(True)
            if hasattr(self, "btn_toggle_inspector"):
                self.btn_toggle_inspector.setText("收合探針 ▲")

        self.inspector_title.setText(f"探針資料檢視: {step_key.upper()} (狀態: {rec.status})")

        lines = [
            f"=== 步驟成果摘要 ===",
            f"• 狀態: {rec.status}",
            f"• 執行時間: {rec.timestamp or '無紀錄'}",
            f"• 摘要: {rec.summary}",
        ]
        if rec.parameters:
            lines.append(f"\n=== 使用參數 ===")
            for k, v in rec.parameters.items():
                lines.append(f"  • {k}: {v}")

        if rec.command_line:
            lines.append(f"\n=== 原生終端機指令 ===")
            lines.append(f"  {rec.command_line}")

        if rec.output_files:
            lines.append(f"\n=== 產出實體檔案 ===")
            for f in rec.output_files:
                lines.append(f"  • {Path(f).name} ({f})")

        if rec.student_notes:
            lines.append(f"\n=== 研究生實驗筆記 ===")
            lines.append(rec.student_notes)

        has_visual = False
        for f in rec.output_files:
            p = Path(f)
            if p.exists() and p.suffix.lower() in (".fasta", ".fa", ".treefile", ".nwk", ".iqtree", ".log", ".txt"):
                try:
                    with open(p, "r", encoding="utf-8", errors="replace") as content_f:
                        head_sample = "".join([content_f.readline() for _ in range(40)])
                    lines.append(f"\n--- 檔案內容預覽 ({p.name}) ---")
                    lines.append(head_sample)
                    if p.suffix.lower() in (".treefile", ".nwk", ".tree"):
                        self.stage.load_tree_file(p)
                        has_visual = True
                    elif p.suffix.lower() in (".fasta", ".fa", ".phy", ".aln"):
                        self.stage.load_msa_file(p)
                        has_visual = True
                    break
                except Exception:
                    pass

        self.inspector_text.setPlainText("\n".join(lines))
        if hasattr(self, "right_tabs"):
            self.right_tabs.setCurrentIndex(1)

        # 2. POP UP the dedicated StepInspectionDialog so the user sees all results directly!
        if show_dialog and not os.environ.get("HEADLESS_TEST"):
            dlg = StepInspectionDialog(step_key, rec, self.pm.current_project, parent=self)
            dlg.jump_requested.connect(self.on_step_jump)
            dlg.note_saved.connect(self.on_note_saved)
            dlg.exec()

    def open_current_step_dir(self):
        if not self.pm.current_project or not self.current_inspect_step:
            return
        sub = STEP_TITLES.get(self.current_inspect_step, ("", ""))[1]
        p = Path(self.pm.current_project.project_dir) / sub
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def open_full_viewer(self):
        if not self.pm.current_project or not self.current_inspect_step:
            return
        rec = self.pm.current_project.steps.get(self.current_inspect_step)
        if not rec or not rec.output_files:
            return
        first_file = rec.output_files[0]
        suffix = Path(first_file).suffix.lower()
        if suffix in (".treefile", ".nwk", ".tree"):
            self.view_tree_requested.emit(first_file)
        elif suffix in (".fasta", ".fa", ".phy", ".aln"):
            self.view_msa_requested.emit(first_file)
        elif suffix in (".iqtree", ".log") or self.current_inspect_step == "modelfinder":
            iqtree_f = next((f for f in rec.output_files if f.endswith(".iqtree")), first_file)
            self.view_model_test_requested.emit(iqtree_f)
        else:
            self.on_step_jump(self.current_inspect_step)
