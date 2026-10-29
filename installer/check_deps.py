# -*- coding: utf-8 -*-
r"""按锁文件核对目标解释器里实际安装的版本。只读，不改环境、不联网。

用法（用被测环境的 python 运行）：
    <venv>/Scripts/python.exe check_deps.py --requirements <lock.txt>
    <venv>/Scripts/python.exe check_deps.py --uv-lock <uv.lock> --pyproject <pyproject.toml>

输出（单行 JSON）：
    {"ok": true, "checked": 6, "missing": [], "mismatch": []}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import metadata
from pathlib import Path


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def installed_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for dist in metadata.distributions():
        try:
            name = dist.metadata["Name"]
            if name:
                out[norm(name)] = dist.version
        except Exception:
            continue
    return out


def parse_requirements(path: Path) -> dict[str, str]:
    want: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([^\s;]+)", line)
        if m:
            want[norm(m.group(1))] = m.group(2)
    return want


def parse_uv_lock(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for block in re.split(r"^\[\[package\]\]\s*$", text, flags=re.M)[1:]:
        n = re.search(r'^name = "([^"]+)"', block, re.M)
        v = re.search(r'^version = "([^"]+)"', block, re.M)
        if n and v:
            out[norm(n.group(1))] = v.group(1)
    return out


def parse_pyproject_deps(path: Path) -> list[str]:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for spec in data.get("project", {}).get("dependencies", []) or []:
        m = re.match(r"^([A-Za-z0-9_.\-]+)", str(spec).strip())
        if m:
            names.append(norm(m.group(1)))
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requirements")
    ap.add_argument("--uv-lock")
    ap.add_argument("--pyproject")
    args = ap.parse_args()

    have = installed_versions()
    want: dict[str, str] = {}
    strict_names: list[str] | None = None

    if args.requirements:
        want = parse_requirements(Path(args.requirements))
        strict_names = list(want.keys())
    elif args.uv_lock:
        locked = parse_uv_lock(Path(args.uv_lock))
        if args.pyproject and Path(args.pyproject).exists():
            strict_names = parse_pyproject_deps(Path(args.pyproject))
        else:
            strict_names = list(locked.keys())
        want = {n: locked[n] for n in locked}
    else:
        print(json.dumps({"ok": False, "checked": 0, "missing": [], "mismatch": [], "error": "no lock given"},
                         ensure_ascii=False))
        return 2

    missing: list[str] = []
    mismatch: list[str] = []
    checked = 0
    for name in strict_names:
        checked += 1
        got = have.get(name)
        exp = want.get(name)
        if got is None:
            missing.append(name)
        elif exp and got != exp:
            mismatch.append(f"{name}({got}!={exp})")
    # 非顶层但已安装的包，版本与锁不一致也算不同步
    for name, exp in want.items():
        if name in strict_names:
            continue
        got = have.get(name)
        if got and exp and got != exp:
            mismatch.append(f"{name}({got}!={exp})")

    ok = not missing and not mismatch
    print(json.dumps({"ok": ok, "checked": checked, "missing": missing, "mismatch": mismatch}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
