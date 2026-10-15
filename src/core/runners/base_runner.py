import subprocess
import threading
from typing import Callable
from pathlib import Path


class CommandRunner:
    """
    Executes a CLI command in a background-friendly manner with live stdout/stderr callback,
    allowing clean cancellation.
    """

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(
        self,
        cmd: list[str],
        cwd: str | Path | None = None,
        log_callback: Callable[[str], None] | None = None,
        stdout_file: str | Path | None = None,
    ) -> tuple[int, str]:
        """
        Runs the command, streaming lines to log_callback.
        If stdout_file is given, stdout is redirected directly to file while stderr is streamed to log_callback.
        Returns (exit_code, full_output).
        """
        self._is_cancelled = False
        output_lines: list[str] = []

        def log(msg: str):
            output_lines.append(msg)
            if log_callback:
                log_callback(msg)

        log(f"[Command] {' '.join(str(c) for c in cmd)}")

        out_fp = None
        try:
            # On Windows, prevent console window flashing
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            if stdout_file:
                stdout_path = Path(stdout_file)
                stdout_path.parent.mkdir(parents=True, exist_ok=True)
                out_fp = open(stdout_path, "w", encoding="utf-8")
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(cwd) if cwd else None,
                    stdout=out_fp,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    startupinfo=startupinfo,
                    bufsize=1,
                )
                stream_pipe = self.process.stderr
            else:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=str(cwd) if cwd else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    startupinfo=startupinfo,
                    bufsize=1,
                )
                stream_pipe = self.process.stdout

            # Read stream line by line
            if stream_pipe:
                for line in iter(stream_pipe.readline, ""):
                    if self._is_cancelled:
                        break
                    line_clean = line.rstrip("\r\n")
                    if line_clean:
                        log(line_clean)

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                    self.process.wait(timeout=2)
                except Exception:
                    pass

            if out_fp:
                out_fp.close()
                out_fp = None

            if self._is_cancelled:
                log("[Cancelled] Process was stopped by user.")
                return -1, "\n".join(output_lines)

            code = self.process.returncode
            if code == 0:
                log("[Success] Finished successfully.")
            else:
                log(f"[Error] Command exited with code {code}.")
            return code, "\n".join(output_lines)

        except Exception as e:
            err_msg = f"[Exception] Failed to execute command: {str(e)}"
            log(err_msg)
            return -1, "\n".join(output_lines)
        finally:
            if out_fp and not out_fp.closed:
                try:
                    out_fp.close()
                except Exception:
                    pass
