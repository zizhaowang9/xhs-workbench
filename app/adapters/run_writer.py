# -*- coding: utf-8 -*-
"""Use the installed XHS Python and restore paths.json environment; no system Python required."""
from pathlib import Path
import subprocess
import sys
from common import load_paths


def main():
    paths = load_paths()
    root = Path(paths["root"])
    python = Path(paths.get("xhs_python") or root / "tools/xiaohongshu-skills/.venv/Scripts/python.exe")
    writer = root / "tools/gpt-writer/gpt_write.py"
    if not python.is_file() or not writer.is_file():
        raise SystemExit("写稿运行环境缺失；请先运行安装.cmd。")
    return subprocess.call([str(python), str(writer), *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
