# -*- coding: utf-8 -*-
"""安装环境公共读取层。

所有路径都从 <安装根>/config/paths.json 派生，方便安装到任意目录。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ADAPTERS_DIR = Path(__file__).resolve().parent
APP_DIR = ADAPTERS_DIR.parent
ROOT_DIR = APP_DIR.parent
CONFIG_PATH = ROOT_DIR / "config" / "paths.json"


def apply_env(paths: dict) -> dict:
    """按 paths.json 恢复本次进程的项目环境（TEMP/TMP、浏览器目录、uv 缓存等）。

    每次新的执行进程都要走这里，不能依赖安装时那个窗口里的临时设置。
    返回实际生效的键值，便于排查。
    """
    root = Path(paths.get("root") or paths.get("project_root") or ROOT_DIR)
    tmp_dir = paths.get("tmp_dir") or str(root / "tmp")
    mapping = {
        "TEMP": tmp_dir,
        "TMP": tmp_dir,
        "PLAYWRIGHT_BROWSERS_PATH": paths.get("playwright_browsers") or str(root / "browsers"),
        "UV_CACHE_DIR": paths.get("uv_cache_dir") or str(root / "cache" / "uv"),
        "UV_PYTHON_INSTALL_DIR": paths.get("python_install_dir") or str(root / "runtime" / "python"),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    applied = {}
    for key, val in mapping.items():
        if not val:
            continue
        if key in ("TEMP", "TMP", "PLAYWRIGHT_BROWSERS_PATH", "UV_CACHE_DIR"):
            try:
                Path(val).mkdir(parents=True, exist_ok=True)
            except OSError:
                continue
        os.environ[key] = str(val)
        applied[key] = str(val)
    return applied


def load_paths() -> dict:
    """读取 paths.json；允许用环境变量 XHS_PATHS 覆盖位置。"""
    cfg = Path(os.environ.get("XHS_PATHS") or CONFIG_PATH)
    if not cfg.exists():
        raise SystemExit(
            f"找不到配置文件：{cfg}\n请先运行安装脚本，或设置环境变量 XHS_PATHS 指向 paths.json"
        )
    data = json.loads(cfg.read_text(encoding="utf-8-sig"))

    # 兼容两种配置结构：
    # - 安装包生成的精简结构（xhs_repo / render_repo / ...）
    # - 早期开发机结构（repo_dir / venv_dir / ...）
    data.setdefault("root", data.get("project_root") or str(ROOT_DIR))
    if not data.get("xhs_repo"):
        data["xhs_repo"] = data.get("repo_dir") or str(Path(data["root"]) / "tools" / "xiaohongshu-skills")
    if not data.get("render_repo"):
        data["render_repo"] = str(Path(data["root"]) / "tools" / "Auto-Redbook-Skills")
    data.setdefault("bridge_url", "ws://localhost:9333")
    data["_config_path"] = str(cfg)
    # 读到配置就恢复本项目环境：每个新进程都生效，不依赖安装时的临时变量
    try:
        data["_env"] = apply_env(data)
    except Exception:
        data["_env"] = {}
    return data


def ensure_repo_importable(paths: dict) -> Path:
    """把小红书操作仓库的 scripts 目录加入 sys.path，并返回该目录。"""
    scripts = Path(paths["xhs_repo"]) / "scripts"
    if not scripts.exists():
        raise SystemExit(f"找不到小红书操作仓库脚本目录：{scripts}")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    return scripts


def load_bridge_module(paths: dict):
    """导入 BridgePage 与登录检查函数。"""
    ensure_repo_importable(paths)
    from xhs.bridge import BridgePage  # noqa: WPS433
    from xhs.login import check_login_status  # noqa: WPS433

    return BridgePage, check_login_status


def make_page(paths: dict):
    BridgePage, _ = load_bridge_module(paths)
    return BridgePage(paths.get("bridge_url", "ws://localhost:9333"))
