import re
from pathlib import Path
from typing import Callable
from dataclasses import dataclass
from src.config import find_tool
from src.core.runners.base_runner import CommandRunner


@dataclass
class IQTreeResult:
    success: bool
    tree_file: str = ""
    iqtree_report: str = ""
    log_file: str = ""
    best_model: str = ""
    timetree_file: str = ""  # .timetree.nex or .timetree.nwk
    lsd_report_file: str = ""
    rate_estimate: str = ""
    tmrca_estimate: str = ""
    message: str = ""

    @property
    def iqtree_file(self) -> str:
        return self.iqtree_report


class IQTreeRunner:
    def __init__(self):
        self.runner = CommandRunner()

    def cancel(self):
        self.runner.cancel()

    def run_inference(
        self,
        input_alignment: str | Path,
        output_prefix: str | Path,
        model: str = "MFP",  # "MFP" (ModelFinder Plus), or specific like "GTR+G+I"
        bootstrap: int = 1000,  # Ultrafast bootstrap
        alrt: int = 1000,  # SH-aLRT test (0 to disable)
        threads: str = "AUTO",
        partition_file: str | Path | None = None,
        date_file: str | Path | None = None,
        date_root: str | None = None,
        date_ci: int = 100,
        date_outlier: float | None = None,
        date_tip: str | None = None,
        user_tree: str | Path | None = None,
        redo: bool = True,
        log_callback: Callable[[str], None] | None = None,
    ) -> IQTreeResult:
        """
        Runs IQ-TREE 2 phylogenetic inference with optional Partitioned Analysis
        and LSD2 Molecular Clock Dating (TimeTree).
        """
        iqtree_exe = find_tool("iqtree3") or find_tool("iqtree2") or find_tool("iqtree")
        if not iqtree_exe:
            msg = "未找到 IQ-TREE (3/2) 執行檔！請前往工具箱一鍵下載安裝。"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return IQTreeResult(success=False, message=msg)

        input_p = Path(input_alignment).resolve()
        if not input_p.exists() or input_p.stat().st_size == 0:
            msg = f"IQ-TREE 輸入檔案不存在或為空: {input_alignment}"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return IQTreeResult(success=False, message=msg)

        prefix_p = Path(output_prefix).resolve()
        prefix_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [iqtree_exe, "-s", str(input_p), "-pre", str(prefix_p)]

        # User topology if provided (-te)
        if user_tree:
            user_tree_p = Path(user_tree).resolve()
            if user_tree_p.exists():
                cmd.extend(["-te", str(user_tree_p)])

        # Substitution Model
        if model:
            cmd.extend(["-m", model])

        # Bootstrap
        if bootstrap > 0:
            cmd.extend(["-B", str(bootstrap)])

        # SH-aLRT
        if alrt > 0:
            cmd.extend(["-alrt", str(alrt)])

        # CPU threads
        if threads:
            cmd.extend(["-T", str(threads)])

        # Partition File
        if partition_file:
            part_p = Path(partition_file).resolve()
            if part_p.exists():
                cmd.extend(["-p", str(part_p)])

        # ================= LSD2 Molecular Clock Dating Options =================
        if date_file:
            df_p = Path(date_file).resolve()
            if df_p.exists():
                cmd.extend(["--date", str(df_p)])
                if date_root:
                    cmd.extend(["--date-root", str(date_root).strip()])
                if date_ci > 0:
                    cmd.extend(["--date-ci", str(date_ci)])
                if date_outlier is not None and date_outlier > 0:
                    cmd.extend(["--date-outlier", str(date_outlier)])
                if date_tip:
                    cmd.extend(["--date-tip", str(date_tip).strip()])

        # Redo
        if redo:
            cmd.append("-redo")

        # Keep identical sequences in alignment without creating reduced uniqueseq datasets
        cmd.append("--keep-ident")

        best_model_found = ""

        def custom_log(line: str):
            nonlocal best_model_found
            if "Best-fit model:" in line or "Best-fit model according to" in line:
                best_model_found = line.strip()
            if log_callback:
                log_callback(line)

        exit_code, full_log = self.runner.run(cmd, cwd=prefix_p.parent, log_callback=custom_log)

        tree_file = Path(f"{prefix_p}.treefile")
        report_file = Path(f"{prefix_p}.iqtree")
        log_file = Path(f"{prefix_p}.log")

        # Check for LSD2 Timetree outputs
        timetree_nex = prefix_p.with_name(f"{prefix_p.name}.timetree.nex")
        timetree_nwk = prefix_p.with_name(f"{prefix_p.name}.timetree.nwk")
        lsd_report = prefix_p.with_name(f"{prefix_p.name}.timetree.lsd")

        timetree_path = ""
        rate_val = ""
        tmrca_val = ""

        if timetree_nex.exists():
            timetree_path = str(timetree_nex)
        elif timetree_nwk.exists():
            timetree_path = str(timetree_nwk)

        if lsd_report.exists():
            try:
                lsd_text = lsd_report.read_text(encoding="utf-8", errors="ignore")
                m_rate = re.search(r"rate\s+([0-9.eE+-]+)", lsd_text)
                if m_rate:
                    rate_val = m_rate.group(1)
                m_tmrca = re.search(r"tMRCA\s+([0-9.eE+-]+)", lsd_text)
                if m_tmrca:
                    tmrca_val = m_tmrca.group(1)
            except Exception:
                pass

        if exit_code == 0 and (tree_file.exists() or timetree_path):
            active_tree = timetree_path if timetree_path else str(tree_file)
            if not best_model_found:
                if report_file.exists():
                    try:
                        rep_txt = report_file.read_text(encoding="utf-8", errors="ignore")
                        m_m = re.search(r"Model of substitution:\s+([^\r\n]+)", rep_txt)
                        if not m_m:
                            m_m = re.search(r"Best-fit model according to BIC:\s+([^\r\n]+)", rep_txt)
                        if m_m:
                            best_model_found = m_m.group(1).strip()
                    except Exception:
                        pass
                if not best_model_found:
                    best_model_found = model

            return IQTreeResult(
                success=True,
                tree_file=active_tree,
                iqtree_report=str(report_file) if report_file.exists() else "",
                log_file=str(log_file) if log_file.exists() else "",
                best_model=best_model_found,
                timetree_file=timetree_path,
                lsd_report_file=str(lsd_report) if lsd_report.exists() else "",
                rate_estimate=rate_val,
                tmrca_estimate=tmrca_val,
                message=f"建樹與定年推論成功完成: {Path(active_tree).name}",
            )

        return IQTreeResult(
            success=False,
            message=f"IQ-TREE 執行失敗 (Exit Code {exit_code})。請參閱日誌以獲得詳細資訊。",
        )
