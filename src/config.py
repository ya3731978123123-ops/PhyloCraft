import os
import sys
import shutil
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
BIN_DIR = BASE_DIR / "bin"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# Ensure directories exist
BIN_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def find_tool(tool_name: str) -> str | None:
    """
    Look for executable in:
    1. Local bin directory
    2. System PATH
    """
    # Windows executable extensions
    exts = [".exe", ".bat", ".cmd", ""] if sys.platform.startswith("win") else [""]
    
    # 1. Check local bin/
    for ext in exts:
        local_path = BIN_DIR / f"{tool_name}{ext}"
        if local_path.is_file():
            return str(local_path)
            
    # Check special nested locations like bin/mafft-win/usr/bin/mafft.bat
    if tool_name == "mafft":
        mafft_nested = list(BIN_DIR.glob("**/mafft.bat")) + list(BIN_DIR.glob("**/mafft.exe"))
        if mafft_nested:
            return str(mafft_nested[0])

    if tool_name in ("iqtree3", "iqtree2", "iqtree"):
        iq_nested = (
            list(BIN_DIR.glob("**/iqtree3.exe"))
            + list(BIN_DIR.glob("**/iqtree2.exe"))
            + list(BIN_DIR.glob("**/iqtree.exe"))
        )
        if i_nested := iq_nested:
            return str(i_nested[0])

    if tool_name == "trimal":
        trimal_nested = list(BIN_DIR.glob("**/trimal.exe"))
        if trimal_nested:
            return str(trimal_nested[0])

    if tool_name == "fasttree":
        ft_nested = list(BIN_DIR.glob("**/fasttree.exe")) + list(BIN_DIR.glob("**/FastTree.exe"))
        if ft_nested:
            return str(ft_nested[0])

    # 2. Check system PATH
    found = shutil.which(tool_name)
    if found:
        return found
        
    return None


def get_tool_status() -> dict[str, dict[str, str | bool]]:
    """Returns availability status and paths for core bio tools."""
    tools = {
        "iqtree": {"name": "IQ-TREE 3 / 2 (ML Tree, ModelFinder & LSD2)", "required": True},
        "mafft": {"name": "MAFFT (Multiple Sequence Alignment)", "required": True},
        "trimal": {"name": "trimAl (Alignment Trimming)", "required": True},
        "fasttree": {"name": "FastTree 2 (Ultra-Fast Tree Inference)", "required": False},
    }
    
    status = {}
    for key, info in tools.items():
        path = find_tool(key)
        status[key] = {
            "name": info["name"],
            "found": path is not None,
            "path": path or "Not found",
        }
    return status
