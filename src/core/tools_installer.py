import io
import os
import re
import shutil
import zipfile
import subprocess
import urllib.request
import json
import sys
from pathlib import Path
from typing import Callable
from src.config import BIN_DIR, find_tool

if sys.platform == "win32":
    import ctypes
    try:
        # SEM_FAILCRITICALERRORS = 1, SEM_NOGPFAULTERRORBOX = 2
        # Suppress modal Windows system error message boxes like "libgcc_s_seh-1.dll not found"
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
    except Exception:
        pass

TOOL_METADATA = {
    "iqtree": {
        "name": "IQ-TREE 3 / 2",
        "role": "世界頂尖最大概似法建樹、MixtureFinder/ModelFinder 模型檢定與 LSD2 分子鐘",
        "default_url": "https://github.com/iqtree/iqtree3/releases/download/v3.1.4/iqtree-3.1.4-Windows.zip",
        "target_file": "iqtree3.exe",
        "github_repo": "iqtree/iqtree3",
    },
    "trimal": {
        "name": "trimAl",
        "role": "全自動多序列比對修剪、Gap/低保守區過濾 (Bioinformatics)",
        "default_url": "https://github.com/inab/trimal/releases/download/v1.5.0/trimAl_Windows_x86-64.zip",
        "target_file": "trimal.exe",
        "pinned_version": "1.5.0",
    },
    "mafft": {
        "name": "MAFFT",
        "role": "高精確度多序列比對演算法，支援核酸/蛋白質/密碼子 (NAR)",
        "default_url": "https://mafft.cbrc.jp/alignment/software/mafft-7.526-win64-signed.zip",
        "target_file": "mafft.bat",
        "web_url": "https://mafft.cbrc.jp/alignment/software/windows_without_cygwin.html",
    },
    "fasttree": {
        "name": "FastTree 2",
        "role": "超大規模資料集（萬條序列）極速最大概似建樹 (PLoS ONE)",
        "default_url": "https://morgannprice.github.io/fasttree/FastTree.exe",
        "target_file": "FastTree.exe",
        "web_url": "https://morgannprice.github.io/fasttree/",
    },
}


def get_installed_tool_version(tool_key: str) -> str:
    """
    Executes local tool and extracts installed version string.
    """
    path = find_tool(tool_key)
    if not path or not Path(path).exists():
        return "未安裝"

    try:
        if tool_key in ("iqtree", "iqtree2", "iqtree3"):
            res = subprocess.run([path, "-v"], capture_output=True, text=True, timeout=5)
            out = res.stdout or res.stderr
            m = re.search(r"version\s+([0-9.]+)", out, re.IGNORECASE)
            return m.group(1) if m else "3.1.4"

        elif tool_key == "trimal":
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            out = res.stdout or res.stderr
            m = re.search(r"trimAl\s+v?([0-9a-zA-Z._-]+)", out, re.IGNORECASE)
            if m:
                raw_v = m.group(1)
                return "1.5.0" if ("1.5.rev0" in raw_v or "1.5.0" in raw_v) else raw_v
            return "1.5.0"

        elif tool_key == "mafft":
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            out = res.stderr or res.stdout
            m = re.search(r"v([0-9.]+)", out)
            return m.group(1) if m else "7.526"

        elif tool_key == "fasttree":
            res = subprocess.run([path, "-help"], capture_output=True, text=True, timeout=5)
            out = res.stderr or res.stdout
            m = re.search(r"FastTree\s+([0-9.]+)", out, re.IGNORECASE)
            return m.group(1) if m else "2.2.0"

    except Exception:
        return "已安裝 (版本未知)"

    return "已安裝"


def query_online_tool_info(tool_key: str) -> dict:
    """
    Queries GitHub API or official vendor web page for latest version, release URL, and download asset.
    """
    if tool_key not in TOOL_METADATA:
        return {"error": f"Unknown tool: {tool_key}"}

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    info = TOOL_METADATA[tool_key]

    if tool_key == "trimal":
        # inab/trimal upstream v1.5.1 Windows release on GitHub broke static linking (missing libgcc_s_seh-1.dll).
        # Pin Windows release to the official standalone static release v1.5.0 (LTS).
        return {
            "latest_version": "1.5.0",
            "release_notes_url": "https://github.com/inab/trimal/releases/tag/v1.5.0",
            "download_url": "https://github.com/inab/trimal/releases/download/v1.5.0/trimAl_Windows_x86-64.zip",
            "error": None,
        }

    if "github_repo" in info:
        repo = info["github_repo"]
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        try:
            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tag = data.get("tag_name", "").lstrip("v")
                html_url = data.get("html_url", "")
                
                # Find appropriate Windows asset
                download_url = ""
                for asset in data.get("assets", []):
                    name_lower = asset["name"].lower()
                    if "windows" in name_lower or "win" in name_lower:
                        download_url = asset["browser_download_url"]
                        break
                
                if not download_url:
                    download_url = info.get("default_url", "")

                return {
                    "latest_version": tag,
                    "release_notes_url": html_url,
                    "download_url": download_url,
                    "error": None,
                }
        except Exception as e:
            # Fallback to defaults
            default_ver = "2.4.0" if tool_key == "iqtree2" else "1.5.1"
            return {
                "latest_version": default_ver,
                "release_notes_url": f"https://github.com/{repo}/releases",
                "download_url": info.get("default_url", ""),
                "error": str(e),
            }

    elif tool_key == "mafft":
        try:
            req = urllib.request.Request(info["web_url"], headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r"mafft-([0-9.]+)-win64", html)
                ver = m.group(1) if m else "7.526"
                return {
                    "latest_version": ver,
                    "release_notes_url": info["web_url"],
                    "download_url": f"https://mafft.cbrc.jp/alignment/software/mafft-{ver}-win64-signed.zip",
                    "error": None,
                }
        except Exception as e:
            return {
                "latest_version": "7.526",
                "release_notes_url": info.get("web_url", ""),
                "download_url": info.get("default_url", ""),
                "error": str(e),
            }

    elif tool_key == "fasttree":
        return {
            "latest_version": "2.2.0",
            "release_notes_url": info["web_url"],
            "download_url": info["default_url"],
            "error": None,
        }

    return {"error": "Unsupported tool query"}


def download_and_extract_tool(
    tool_key: str,
    download_url: str | None = None,
    progress_callback: Callable[[int, str], None] | None = None,
) -> tuple[bool, str]:
    """
    Downloads and extracts a tool's pre-compiled binary into the local bin/ directory.
    Supports both .zip bundles and direct .exe executables.
    """
    if tool_key not in TOOL_METADATA:
        return False, f"Unknown tool: {tool_key}"

    tool_info = TOOL_METADATA[tool_key]
    url = download_url or tool_info["default_url"]
    name = tool_info["name"]

    BIN_DIR.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback(5, f"連線至 {name} 官方伺服器下載中...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=40) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            chunk_size = 1024 * 64
            buffer = io.BytesIO()

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                buffer.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    pct = int(10 + (downloaded / total_size) * 75)
                    progress_callback(pct, f"下載 {name}: {downloaded // 1024} KB / {total_size // 1024} KB")

        buffer_bytes = buffer.getvalue()
        
        # Check if direct Windows executable (PE header 'MZ')
        if buffer_bytes[:2] == b"MZ" or url.lower().endswith(".exe"):
            if progress_callback:
                progress_callback(90, f"部署 {name} 執行檔至 bin/ 目錄...")
            target_path = BIN_DIR / tool_info["target_file"]
            with open(target_path, "wb") as f:
                f.write(buffer_bytes)
        else:
            # Handle ZIP archives
            if progress_callback:
                progress_callback(88, f"解壓縮 {name} 壓縮檔中...")

            buffer.seek(0)
            with zipfile.ZipFile(buffer) as z:
                if tool_key == "mafft":
                    extract_dir = BIN_DIR / "mafft-win"
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    z.extractall(extract_dir)
                elif tool_key in ("iqtree", "iqtree2", "iqtree3"):
                    for member in z.namelist():
                        if member.endswith("iqtree3.exe") or member.endswith("iqtree2.exe") or member.endswith(".dll"):
                            filename = os.path.basename(member)
                            with z.open(member) as source, open(BIN_DIR / filename, "wb") as target:
                                shutil.copyfileobj(source, target)
                elif tool_key == "trimal":
                    for member in z.namelist():
                        if member.endswith("trimal.exe") or member.endswith(".dll"):
                            filename = os.path.basename(member)
                            with z.open(member) as source, open(BIN_DIR / filename, "wb") as target:
                                shutil.copyfileobj(source, target)

        if progress_callback:
            progress_callback(100, f"{name} 安裝/更新成功！")

        return True, f"{name} 已成功就緒，可立即執行分析。"

    except Exception as e:
        err = f"下載/安裝 {name} 失敗: {str(e)}"
        if progress_callback:
            progress_callback(0, err)
        return False, err


def test_tool_execution(tool_key: str) -> tuple[bool, str]:
    """
    Runs a fast diagnostic check on the installed tool.
    """
    path = find_tool(tool_key)
    if not path:
        return False, f"未找到 {tool_key} 執行檔，請先執行下載安裝。"

    try:
        if tool_key in ("iqtree", "iqtree2", "iqtree3"):
            res = subprocess.run([path, "-v"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0, res.stdout or res.stderr
        elif tool_key == "trimal":
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0, res.stdout or res.stderr
        elif tool_key == "mafft":
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            return True, res.stderr or res.stdout
        elif tool_key == "fasttree":
            res = subprocess.run([path, "-help"], capture_output=True, text=True, timeout=5)
            return res.returncode == 0, (res.stderr or res.stdout)[:200]
    except Exception as e:
        return False, str(e)

    return False, "未知測試結果"
