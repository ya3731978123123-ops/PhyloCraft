from pathlib import Path
from typing import Callable
from src.config import find_tool
from src.core.runners.base_runner import CommandRunner


class TrimalRunner:
    def __init__(self):
        self.runner = CommandRunner()

    def cancel(self):
        self.runner.cancel()

    def run_trimming(
        self,
        input_alignment: str | Path,
        output_alignment: str | Path,
        method: str = "automated1",  # "automated1", "gappyout", "strict", "strictplus", "custom"
        gap_threshold: float = 0.8,
        similarity_threshold: float = 0.001,
        save_html: bool = False,
        log_callback: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Runs trimAl for alignment trimming.
        """
        trimal_exe = find_tool("trimal")
        if not trimal_exe:
            msg = "trimAl executable not found! Please check Tool Manager or install trimAl."
            if log_callback:
                log_callback(f"[Error] {msg}")
            return False, msg

        input_p = Path(input_alignment).resolve()
        if not input_p.exists() or input_p.stat().st_size == 0:
            msg = f"trimAl 輸入檔案不存在或為空: {input_alignment}"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return False, msg

        output_p = Path(output_alignment).resolve()
        output_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [trimal_exe, "-in", str(input_p), "-out", str(output_p)]

        if method == "automated1":
            cmd.append("-automated1")
        elif method == "gappyout":
            cmd.append("-gappyout")
        elif method == "strict":
            cmd.append("-strict")
        elif method == "strictplus":
            cmd.append("-strictplus")
        elif method == "custom":
            cmd.extend(["-gt", str(gap_threshold)])
            cmd.extend(["-st", str(similarity_threshold)])

        if save_html:
            html_p = output_p.with_suffix(".html")
            cmd.extend(["-htmlout", str(html_p)])

        exit_code, _ = self.runner.run(cmd, cwd=input_p.parent, log_callback=log_callback)

        if exit_code == 0 and output_p.exists():
            if output_p.stat().st_size == 0:
                return False, f"trimAl 修剪過濾後為空檔案 (0 bytes)，位點全部被剔除，請使用較寬鬆之修剪門檻 (例如 gappyout)！"
            return True, f"Trimmed alignment saved to {output_p.name}"
        return False, f"trimAl failed with code {exit_code}"
