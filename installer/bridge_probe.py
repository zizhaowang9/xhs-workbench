# -*- coding: utf-8 -*-
"""Bridge 归属探测（只读）。

连一下 ws://localhost:<port>，发 ping_server，读服务自己上报的安装根与扩展状态。
不启动、不关闭、不改动任何进程，用于判断「端口上这个 Bridge 是不是本安装目录的」。

输出（单行 JSON）：
    {"reachable": true, "root": "D:\\XHSWork", "extension": false, "pid": 1234, "error": ""}

旧版本 Bridge 不回报 root 时，root 为 null —— 调用方应按「归属不明」处理。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--timeout", type=float, default=3.0)
    ap.add_argument("--root", default=None)
    ap.add_argument("--script", default=None)
    ap.add_argument("--observed-script", default=None)
    args = ap.parse_args()

    out = {"reachable": False, "root": None, "extension": None, "pid": None, "script_path": None, "error": ""}
    out.update(expected_root=None, expected_script_path=None, observed_script_path=None)
    try:
        # Resolve local expectations using the same Windows path rules as the server.
        # These values come from our caller, not from the listening process.
        for key, value in (("expected_root", args.root),
                           ("expected_script_path", args.script),
                           ("observed_script_path", args.observed_script)):
            if value:
                out[key] = str(Path(value).resolve())
        from websockets.sync.client import connect

        with connect(f"ws://localhost:{args.port}", open_timeout=args.timeout, close_timeout=1) as ws:
            ws.send(json.dumps({"role": "cli", "method": "ping_server"}))
            raw = ws.recv(timeout=args.timeout)
        msg = json.loads(raw)
        res = msg.get("result") if isinstance(msg, dict) else None
        if not isinstance(res, dict) or not isinstance(res.get("extension_connected"), bool):
            raise ValueError("Invalid ping_server response")
        out["reachable"] = True
        out["root"] = res.get("root")
        ext = res.get("extension_connected")
        out["extension"] = None if ext is None else bool(ext)
        out["pid"] = res.get("pid")
        out["script_path"] = res.get("script_path")
    except Exception as exc:  # 连不上就是连不上，如实返回
        out["error"] = f"{type(exc).__name__}: {exc}"

    # ASCII JSON survives redirected Windows code pages; JSON readers restore Unicode.
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

