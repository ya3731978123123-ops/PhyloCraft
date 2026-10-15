from pathlib import Path
from typing import Callable
from src.config import find_tool
from src.core.runners.base_runner import CommandRunner


class MafftRunner:
    def __init__(self):
        self.runner = CommandRunner()

    def cancel(self):
        self.runner.cancel()

    def run_alignment(
        self,
        input_fasta: str | Path,
        output_fasta: str | Path,
        algorithm: str = "auto",  # "auto", "fft-ns-2", "linsi", "einsi", "ginsi"
        adjust_direction: bool = False,
        threads: int = -1,
        log_callback: Callable[[str], None] | None = None,
    ) -> tuple[bool, str]:
        """
        Runs MAFFT alignment.
        Writes aligned sequences to output_fasta.
        """
        mafft_exe = find_tool("mafft")
        if not mafft_exe:
            msg = "MAFFT executable not found! Please check Tool Manager or install MAFFT."
            if log_callback:
                log_callback(f"[Error] {msg}")
            return False, msg

        input_p = Path(input_fasta).resolve()
        if not input_p.exists() or input_p.stat().st_size == 0:
            msg = f"MAFFT 輸入檔案不存在或為空: {input_fasta}"
            if log_callback:
                log_callback(f"[Error] {msg}")
            return False, msg

        output_p = Path(output_fasta).resolve()
        output_p.parent.mkdir(parents=True, exist_ok=True)

        cmd = [mafft_exe]

        if algorithm == "auto":
            cmd.append("--auto")
        elif algorithm == "linsi":
            cmd.append("--localpair")
            cmd.extend(["--maxiterate", "1000"])
        elif algorithm == "einsi":
            cmd.append("--genafpair")
            cmd.extend(["--maxiterate", "1000"])
        elif algorithm == "ginsi":
            cmd.append("--globalpair")
            cmd.extend(["--maxiterate", "1000"])
        elif algorithm == "fft-ns-2":
            cmd.append("--retree")
            cmd.append("2")

        if adjust_direction:
            cmd.append("--adjustdirection")

        if threads != 0:
            cmd.extend(["--thread", str(threads)])

        cmd.append(str(input_p))

        # Run MAFFT with stdout redirected directly to output_p, streaming stderr logs to log_callback
        exit_code, full_log = self.runner.run(
            cmd,
            cwd=input_p.parent,
            log_callback=log_callback,
            stdout_file=output_p,
        )

        if exit_code == 0:
            if output_p.exists() and output_p.stat().st_size > 0:
                return True, f"Alignment saved to {output_p.name}"
            return False, "MAFFT finished but output alignment file is empty."
        return False, f"MAFFT failed with code {exit_code}"
