from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QComboBox,
    QSpinBox,
    QProgressBar,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices

from src.config import OUTPUT_DIR, DATA_DIR
from src.core.sanitizer import sanitize_fasta_file, save_sanitized_fasta
from src.core.runners.mafft_runner import MafftRunner
from src.core.runners.trimal_runner import TrimalRunner
from src.core.runners.modelfinder_runner import ModelFinderRunner
from src.core.runners.iqtree_runner import IQTreeRunner
from src.ui.widgets.log_viewer import LogViewer


class PipelineWorker(QThread):
    progress_signal = Signal(int, str)
    log_signal = Signal(str)
    finished_signal = Signal(bool, str, str, str, str)  # success, tree_path, aln_path, best_model, message

    def __init__(
        self,
        input_fasta: str,
        output_dir: str,
        trimal_method: str = "automated1",
        model: str = "MFP",
        bootstrap: int = 1000,
        alrt: int = 1000,
    ):
        super().__init__()
        self.input_fasta = Path(input_fasta)
        self.output_dir = Path(output_dir)
        self.trimal_method = trimal_method
        self.model = model
        self.bootstrap = bootstrap
        self.alrt = alrt
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

    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            stem = self.input_fasta.stem

            # Step 1: Sanitize
            self.progress_signal.emit(10, "步驟 1/5: 檢查序列與清洗標頭非法字元...")
            self.log_signal.emit("[步驟 1/5] 檢查序列與清洗標頭非法字元...")

            san_res = sanitize_fasta_file(self.input_fasta)
            if not san_res.success:
                self.finished_signal.emit(False, "", "", "", f"序列檢查失敗: {san_res.warnings}")
                return

            self.log_signal.emit(
                f"[成功] 載入 {san_res.total_taxa} 個物種/個體 ({san_res.seq_type})。 "
                f"長度區間: {san_res.min_length} ~ {san_res.max_length} bp。"
            )
            for orig, clean in san_res.id_mapping.items():
                self.log_signal.emit(f"[已修正標頭] '{orig}' -> '{clean}'")

            clean_fasta = self.output_dir / f"{stem}_cleaned.fasta"
            save_sanitized_fasta(san_res.cleaned_records, clean_fasta)

            if self.is_cancelled:
                return

            # Step 2: MAFFT Alignment
            self.progress_signal.emit(30, "步驟 2/5: 執行 MAFFT 高品質多重序列比對...")
            self.log_signal.emit("[步驟 2/5] 執行 MAFFT 多序列比對中...")
            aligned_fasta = self.output_dir / f"{stem}_aligned.fasta"

            ok, msg = self.mafft_runner.run_alignment(
                clean_fasta,
                aligned_fasta,
                algorithm="auto",
                log_callback=self.log_signal.emit,
            )
            if not ok or not aligned_fasta.exists():
                self.finished_signal.emit(False, "", "", "", f"MAFFT 比對失敗: {msg}")
                return

            if self.is_cancelled:
                return

            # Step 3: trimAl Trimming
            self.progress_signal.emit(50, "步驟 3/5: 執行 trimAl 智慧修剪與空缺過濾...")
            self.log_signal.emit(f"[步驟 3/5] 執行 trimAl 修剪 ({self.trimal_method})...")
            trimmed_fasta = self.output_dir / f"{stem}_trimmed.fasta"

            ok, msg = self.trimal_runner.run_trimming(
                aligned_fasta,
                trimmed_fasta,
                method=self.trimal_method,
                log_callback=self.log_signal.emit,
            )
            if not ok or not trimmed_fasta.exists():
                self.finished_signal.emit(False, "", "", "", f"trimAl 修剪失敗: {msg}")
                return

            if self.is_cancelled:
                return

            # Step 4: ModelFinder Model Selection
            best_model = self.model
            if self.model in ("MFP", "AUTO", "") or "MF" in self.model:
                self.progress_signal.emit(70, "步驟 4/5: 【全自動】ModelFinder 最佳替代模型統計檢定 (BIC/AIC)...")
                self.log_signal.emit("[步驟 4/5: 全自動模型檢定] 系統正自動評比 88+ 種演化替代模型...")
                mf_prefix = self.output_dir / f"{stem}_modelfinder"
                mf_res = self.mf_runner.run_modelfinder(
                    trimmed_fasta,
                    mf_prefix,
                    search_scope="TESTONLY",
                    threads="AUTO",
                    log_callback=self.log_signal.emit,
                )
                if mf_res.success and mf_res.best_model:
                    best_model = mf_res.best_model
                    self.log_signal.emit(f"[步驟 4/5 成果] 系統已全自動選定最佳替代模型: {best_model} (BIC 統計最優解)")
                    if mf_res.candidate_models:
                        top_info = " | ".join(f"#{c.rank} {c.model} (ΔBIC={c.delta_bic:.1f})" for c in mf_res.candidate_models[:3])
                        self.log_signal.emit(f"[步驟 4/5 候選排行] {top_info}")
                else:
                    best_model = "GTR+G+I"
                    self.log_signal.emit(f"[步驟 4/5 備用] 使用標準通用替代模型: {best_model}")
            else:
                self.progress_signal.emit(70, f"步驟 4/5: 指定替代模型: {best_model}")
                self.log_signal.emit(f"[步驟 4/5] 使用指定替代模型: {best_model}")

            if self.is_cancelled:
                return

            # Step 5: IQ-TREE Tree Building
            self.progress_signal.emit(90, f"步驟 5/5: 執行 IQ-TREE 最大概似法建樹 (模型: {best_model})...")
            self.log_signal.emit(f"[步驟 5/5] 執行 IQ-TREE 最大概似法建樹 (設定模型: {best_model}, 1000 次 UFBoot)...")
            tree_prefix = self.output_dir / f"{stem}_tree"

            iq_res = self.iqtree_runner.run_inference(
                trimmed_fasta,
                tree_prefix,
                model=best_model,
                bootstrap=self.bootstrap,
                alrt=self.alrt,
                log_callback=self.log_signal.emit,
            )

            if not iq_res.success:
                self.finished_signal.emit(False, "", str(trimmed_fasta), best_model, iq_res.message)
                return

            self.progress_signal.emit(100, f"分析完成！最佳模式: {best_model} | 發表級演化樹已產出。")
            self.log_signal.emit(f"[成功] 最佳取代模式: {best_model}")
            self.log_signal.emit(f"[成功] 樹檔路徑: {iq_res.tree_file}")
            self.finished_signal.emit(True, iq_res.tree_file, str(trimmed_fasta), best_model, "黃金管線 5 步全流程圓滿完成！")

        except Exception as e:
            self.finished_signal.emit(False, "", "", "", f"發生非預期錯誤: {str(e)}")


class PipelineTab(QWidget):
    """
    One-Click Golden Pipeline:
    Upload FASTA -> Sanitize -> MAFFT -> trimAl -> IQ-TREE 2 -> Ready!
    """

    view_tree_requested = Signal(str)
    view_msa_requested = Signal(str)
    test_model_requested = Signal(str)
    pipeline_finished_with_details = Signal(str, str, str, str)  # input_fasta, tree_path, aln_path, best_model

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.worker: PipelineWorker | None = None
        self.last_tree_file: str = ""
        self.last_aligned_file: str = ""
        self.last_best_model: str = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header banner (Sleek single-line with info badge)
        title_box = QFrame()
        title_box.setStyleSheet("background-color: #f8fafc; border-radius: 8px; padding: 10px 14px; border: 1px solid #e2e8f0;")
        tb_layout = QHBoxLayout(title_box)
        tb_layout.setContentsMargins(0, 0, 0, 0)

        t_vbox = QVBoxLayout()
        t_vbox.setSpacing(2)
        h_title = QLabel("<b>自動化分析流程 (Automated Phylogenomics Pipeline)</b>")
        h_title.setStyleSheet("color: #0f172a; font-size: 14px;")
        t_vbox.addWidget(h_title)

        h_sub = QLabel("依序執行序列檢查 -> MAFFT 多重比對 -> trimAl 保守位點修剪 -> ModelFinder 最優模型檢定 -> IQ-TREE 2 最大概似法建樹")
        h_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        t_vbox.addWidget(h_sub)
        tb_layout.addLayout(t_vbox, 1)

        info_btn = QLabel("期刊標準流程")
        info_btn.setStyleSheet("color: #006644; background-color: #f1f5f9; padding: 4px 10px; border-radius: 12px; font-size: 11px; border: 1px solid #cbd5e1;")
        info_btn.setToolTip(
            "國際期刊演化學標準作業流程 (Standard Systematic Biology Protocol):\n"
            "① 序列品管與清洗: 自動過濾標頭特殊字元，統計 GC% 與長度分佈。\n"
            "② 多重序列比對 (MSA): MAFFT (Katoh & Standley, 2013) 高品質對齊。\n"
            "③ 品質修剪 (Trimming): trimAl -automated1 智慧去除 Gap 雜訊。\n"
            "④ 分子模型評估: ModelFinder 檢驗 80+ 模型並依 BIC 挑選最優解。\n"
            "⑤ 系統發育重建: IQ-TREE 2 最大概似法 + 1,000 次 UFBoot2 + SH-aLRT 雙重檢驗。\n"
            "⑥ 論文成果導出: 自動生成 Materials & Methods 英文段落與高解析度帶尺標插圖。"
        )
        tb_layout.addWidget(info_btn)

        layout.addWidget(title_box)

        # File Selection Group
        files_box = QGroupBox("檔案設定 (File Setup)")
        f_layout = QVBoxLayout(files_box)

        # Input FASTA
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("原始 FASTA 檔案:"))
        self.input_edit = QLineEdit()
        self.input_edit.setMinimumHeight(28)
        self.input_edit.setPlaceholderText("請選取或直接將 .fasta, .fas, .fa 檔案拖曳進來...")
        in_row.addWidget(self.input_edit)

        browse_btn = QPushButton("瀏覽 (Browse)...")
        browse_btn.clicked.connect(self.browse_input)
        in_row.addWidget(browse_btn)

        sample_btn = QPushButton("載入範例資料")
        sample_btn.setToolTip("載入內建的靈長類細胞色素 b (Cytb) 測試序列")
        sample_btn.clicked.connect(self.load_sample)
        in_row.addWidget(sample_btn)
        f_layout.addLayout(in_row)

        # Output Folder
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("結果輸出資料夾:"))
        self.output_edit = QLineEdit(str(OUTPUT_DIR))
        self.output_edit.setMinimumHeight(28)
        out_row.addWidget(self.output_edit)

        out_browse = QPushButton("更改位置...")
        out_browse.clicked.connect(self.browse_output)
        out_row.addWidget(out_browse)

        f_layout.addLayout(out_row)
        layout.addWidget(files_box)

        # Parameters Group
        param_box = QGroupBox("分析參數與設定 (Pipeline Parameters)")
        p_layout = QHBoxLayout(param_box)

        # trimAl method
        p_layout.addWidget(QLabel("修剪策略:"))
        self.trimal_combo = QComboBox()
        self.trimal_combo.setMinimumHeight(28)
        self.trimal_combo.addItems([
            "automated1 (啟發式平衡修剪)",
            "gappyout (去除高 Gap 比例位點)",
            "strict (嚴格修剪 - 僅保留高保守度區域)",
            "strictplus (極端嚴格 - 適用高分化度序列)",
        ])
        self.trimal_combo.setToolTip("automated1 專為 ML 建樹設計，能在保留有效訊號的同時去除雜訊")
        p_layout.addWidget(self.trimal_combo)

        # Substitution Model
        p_layout.addWidget(QLabel("取代模式 (Model):"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(28)
        self.model_combo.addItems([
            "全自動最佳化 (ModelFinder 自動檢驗 88+ 種模式並選出 BIC 最優解)",
            "GTR+G+I (手動指定 - 核酸全參數模型)",
            "HKY+G (手動指定 - 快速核酸模型)",
            "WAG+G+I (手動指定 - 通用蛋白質模型)",
            "LG+G+I (手動指定 - 高精確蛋白質模型)",
            "JTT+G (手動指定 - 常用蛋白質模型)",
        ])
        self.model_combo.setToolTip("預設為「全自動最佳化」：自動評比 88+ 種演化模型，依 BIC 標準挑選最佳模型建樹。")
        p_layout.addWidget(self.model_combo)

        # Bootstrap
        p_layout.addWidget(QLabel("拔靴檢驗 (UFBoot):"))
        self.boot_spin = QSpinBox()
        self.boot_spin.setMinimumHeight(28)
        self.boot_spin.setRange(0, 10000)
        self.boot_spin.setValue(1000)
        self.boot_spin.setSingleStep(500)
        self.boot_spin.setToolTip("Ultrafast Bootstrap 次數，建議維持 1000 次（數值 >70% 代表分支可信）")
        p_layout.addWidget(self.boot_spin)

        p_layout.addStretch()
        layout.addWidget(param_box)

        # Action Buttons (Row 1: Execute/Cancel, Row 2: Results & Exploration)
        r1_action = QHBoxLayout()
        r1_action.setSpacing(10)
        self.start_btn = QPushButton("開始執行分析流程 (Run Pipeline)")
        self.start_btn.setObjectName("primary_button")
        self.start_btn.setFixedHeight(38)
        self.start_btn.clicked.connect(self.start_pipeline)
        r1_action.addWidget(self.start_btn, 4)

        self.cancel_btn = QPushButton("停止 (Stop)")
        self.cancel_btn.setObjectName("danger_button")
        self.cancel_btn.setFixedHeight(38)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_pipeline)
        r1_action.addWidget(self.cancel_btn, 1)
        layout.addLayout(r1_action)

        r2_action = QHBoxLayout()
        r2_action.setSpacing(8)

        self.view_msa_btn = QPushButton("檢視比對 (View MSA)")
        self.view_msa_btn.setFixedHeight(34)
        self.view_msa_btn.setEnabled(False)
        self.view_msa_btn.setToolTip("在色彩矩陣中檢視比對完成與修剪後的序列")
        self.view_msa_btn.clicked.connect(self.open_msa_view)
        r2_action.addWidget(self.view_msa_btn)

        self.view_model_btn = QPushButton("模型檢定 (ModelFinder)")
        self.view_model_btn.setFixedHeight(34)
        self.view_model_btn.setEnabled(False)
        self.view_model_btn.setToolTip("查看詳細的 ModelFinder 候選模型評分表與演化參數")
        self.view_model_btn.clicked.connect(self.open_model_view)
        r2_action.addWidget(self.view_model_btn)

        self.view_tree_btn = QPushButton("檢視演化樹 (View Tree)")
        self.view_tree_btn.setFixedHeight(34)
        self.view_tree_btn.setEnabled(False)
        self.view_tree_btn.setToolTip("切換至樹圖檢視器進行外群定根與高清輸出")
        self.view_tree_btn.clicked.connect(self.open_tree_view)
        r2_action.addWidget(self.view_tree_btn)

        self.report_btn = QPushButton("分析報告 (Paper Report)")
        self.report_btn.setFixedHeight(34)
        self.report_btn.setEnabled(False)
        self.report_btn.setStyleSheet("color: #006644; font-weight: bold;")
        self.report_btn.setToolTip("生成國際期刊標準 Materials & Methods 英文段落、BIC 模型比較表與 BibTeX")
        self.report_btn.clicked.connect(self.open_academic_report)
        r2_action.addWidget(self.report_btn)

        self.result_dir_btn = QPushButton("開啟成果資料夾 (Open Folder)")
        self.result_dir_btn.setFixedHeight(34)
        self.result_dir_btn.setEnabled(False)
        self.result_dir_btn.clicked.connect(self.open_output_dir)
        self.open_dir_btn = self.result_dir_btn
        r2_action.addWidget(self.result_dir_btn)

        layout.addLayout(r2_action)

        # Results Summary Card (Shown when pipeline finishes)
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #f0fdf4;
                border: 1px solid #86efac;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        self.summary_frame.setVisible(False)
        sf_layout = QHBoxLayout(self.summary_frame)
        sf_layout.setContentsMargins(8, 4, 8, 4)

        self.summary_text = QLabel("分析成果摘要: 等待執行...")
        self.summary_text.setStyleSheet("color: #15803d; font-size: 13px; font-weight: bold;")
        sf_layout.addWidget(self.summary_text, 1)

        layout.addWidget(self.summary_frame)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("準備就緒 (Ready)")
        layout.addWidget(self.progress_bar)

        # Log Viewer
        self.log_viewer = LogViewer("管線即時日誌 (Pipeline Log Console)")
        layout.addWidget(self.log_viewer, 1)

    def browse_input(self):
        fp, _ = QFileDialog.getOpenFileName(
            self, "選取輸入 FASTA 檔案", "", "FASTA 檔案 (*.fasta *.fa *.fas *.fna *.faa);;所有檔案 (*)"
        )
        if fp:
            self.input_edit.setText(fp)

    def load_sample(self):
        sample_path = DATA_DIR / "primates_cytb.fasta"
        if sample_path.exists():
            self.input_edit.setText(str(sample_path))
            self.log_viewer.append_log(f"[資訊] 已載入內建範例數據: {sample_path.name}")
        else:
            QMessageBox.warning(self, "範例遺失", "找不到範例檔案。")

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "選取輸出資料夾", self.output_edit.text())
        if folder:
            self.output_edit.setText(folder)

    def open_output_dir(self):
        out_dir = self.output_edit.text().strip() or str(OUTPUT_DIR)
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def start_pipeline(self):
        fasta_path = self.input_edit.text().strip()
        if not fasta_path or not Path(fasta_path).exists():
            QMessageBox.warning(self, "警告", "請先選取有效的 FASTA 檔案。")
            return

        out_dir = self.output_edit.text().strip() or str(OUTPUT_DIR)

        trimal_choice = self.trimal_combo.currentText().split()[0]
        model_raw = self.model_combo.currentText()
        if "全自動" in model_raw or "MFP" in model_raw or "ModelFinder" in model_raw:
            model_choice = "MFP"
        else:
            model_choice = model_raw.split()[0]
        boot_reps = self.boot_spin.value()

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.view_tree_btn.setEnabled(False)
        self.view_msa_btn.setEnabled(False)
        self.report_btn.setEnabled(False)
        self.result_dir_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("管線啟動中...")
        self.log_viewer.clear_log()

        self.worker = PipelineWorker(
            input_fasta=fasta_path,
            output_dir=out_dir,
            trimal_method=trimal_choice,
            model=model_choice,
            bootstrap=boot_reps,
        )
        self.worker.progress_signal.connect(self.on_progress)
        self.worker.log_signal.connect(self.log_viewer.append_log)
        self.worker.finished_signal.connect(self.on_pipeline_finished)
        self.worker.start()

    def cancel_pipeline(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log_viewer.append_log("[已取消] 使用者手動終止分析...")
            self.cancel_btn.setEnabled(False)

    def on_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}% - {msg}")

    def on_pipeline_finished(self, success: bool, tree_path: str, aln_path: str, best_model: str, msg: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        if success:
            self.last_tree_file = tree_path
            self.last_aligned_file = aln_path
            self.last_best_model = best_model
            self.view_tree_btn.setEnabled(True)
            self.view_msa_btn.setEnabled(bool(aln_path))
            self.view_model_btn.setEnabled(bool(aln_path))
            self.report_btn.setEnabled(True)
            self.result_dir_btn.setEnabled(True)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("全流程 5 步驟已完成")

            self.summary_frame.setVisible(True)
            self.summary_text.setText(
                f"[完成] 分析已完成。 演化樹: {Path(tree_path).name} | 最佳替代模型 (BIC): {best_model} | 可點選上方按鈕查看詳情。"
            )
            self.pipeline_finished_with_details.emit(
                self.input_edit.text().strip(), tree_path, aln_path, best_model
            )

            QMessageBox.information(
                self,
                "分析完成",
                f"國際期刊五部曲全流程已完成。\n\n"
                f"• 最優替代模型: {best_model}\n"
                f"• 演化樹檔案: {Path(tree_path).name}\n"
                f"• 修剪後比對: {Path(aln_path).name}\n\n"
                f"可點選上方「檢視演化樹」、「模型檢定」或「論文方法與報告」產出論文成果。"
            )
        else:
            self.progress_bar.setFormat("分析失敗")
            QMessageBox.critical(self, "錯誤", f"管線中斷:\n{msg}")

    def open_model_view(self):
        if self.last_aligned_file:
            self.test_model_requested.emit(self.last_aligned_file)

    def open_tree_view(self):
        if self.last_tree_file:
            self.view_tree_requested.emit(self.last_tree_file)

    def open_msa_view(self):
        if self.last_aligned_file:
            self.view_msa_requested.emit(self.last_aligned_file)

    def open_academic_report(self):
        if not self.last_tree_file:
            return
        iqtree_file = Path(self.last_tree_file).with_suffix(".iqtree")
        if not iqtree_file.exists():
            clean_str = str(self.last_tree_file).replace(".timetree.nwk", ".iqtree").replace(".timetree.nex", ".iqtree")
            cand = Path(clean_str)
            if cand.exists():
                iqtree_file = cand
            else:
                p_cands = list(Path(self.last_tree_file).parent.glob("*.iqtree"))
                if p_cands:
                    iqtree_file = p_cands[0]
                else:
                    QMessageBox.warning(self, "報告遺失", f"找不到對應的 IQ-TREE 分析報告:\n{iqtree_file.name}")
                    return

        from src.core.iqtree_parser import parse_iqtree_report
        from src.ui.widgets.report_dialog import PublicationReportDialog

        report_data = parse_iqtree_report(iqtree_file)
        if report_data.success:
            dialog = PublicationReportDialog(report_data, self)
            dialog.exec()
        else:
            QMessageBox.critical(self, "解析失敗", "無法解析 IQ-TREE 報告檔。")
