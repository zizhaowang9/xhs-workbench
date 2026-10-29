# -*- coding: utf-8 -*-
"""渲染统一入口：先按本机配置恢复 TEMP/TMP、Chromium 目录，再调用 render_xhs.py。

    python run_render.py --cards <工作目录>\\cards.md --output-dir <工作目录>\\images --theme sketch
    python run_render.py --print-env          # 只打印本次进程实际生效的环境

技能和脚本都走这里：每个新进程都会重新读配置，不依赖安装时那个窗口里的临时变量。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from common import load_paths

KEYS = ("TEMP", "TMP", "PLAYWRIGHT_BROWSERS_PATH", "PYTHONUTF8", "PYTHONIOENCODING")


def main() -> int:
    ap = argparse.ArgumentParser(description="按本机配置恢复环境后渲染卡片")
    ap.add_argument("--cards")
    ap.add_argument("--output-dir")
    ap.add_argument("--theme", default="default")
    ap.add_argument("--mode", default="auto-fit")
    ap.add_argument("--width", default="1080")
    ap.add_argument("--height", default="1440")
    ap.add_argument("--dpr", default="1")
    ap.add_argument("--print-env", action="store_true", help="只打印本次进程生效的环境变量")
    ap.add_argument("passthrough", nargs=argparse.REMAINDER, help="原样传给 render_xhs.py 的额外参数")
    args = ap.parse_args()

    paths = load_paths()
    env_now = {k: os.environ.get(k, "") for k in KEYS}

    if args.print_env:
        print(f"配置：{paths.get('_config_path')}")
        for k, v in env_now.items():
            print(f"{k}={v}")
        return 0

    if not args.cards or not args.output_dir:
        ap.error("需要 --cards 与 --output-dir（或用 --print-env 只看环境）")

    render_py = paths.get("render_python")
    render_repo = paths.get("render_repo")
    if not render_py or not Path(render_py).exists():
        raise SystemExit(f"找不到渲染解释器：{render_py}（先运行安装或「检查环境.cmd」）")
    script = Path(render_repo or "") / "scripts" / "render_xhs.py"
    if not script.exists():
        raise SystemExit(f"找不到渲染脚本：{script}")

    extra = [a for a in (args.passthrough or []) if a != "--"]
    cmd = [
        str(render_py), str(script), str(args.cards),
        "--output-dir", str(args.output_dir),
        "--theme", str(args.theme),
        "--mode", str(args.mode),
        "--width", str(args.width),
        "--height", str(args.height),
        "--dpr", str(args.dpr),
    ] + extra
    print(f"环境：TEMP={env_now['TEMP']}")
    print(f"      PLAYWRIGHT_BROWSERS_PATH={env_now['PLAYWRIGHT_BROWSERS_PATH']}")
    print(f"渲染：{' '.join(cmd)}")
    sys.stdout.flush()
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
