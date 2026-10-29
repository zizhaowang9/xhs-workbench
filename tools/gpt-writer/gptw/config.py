# -*- coding: utf-8 -*-
"""配置加载（服务地址 / 模型 / 协议 / 限额 / 密钥来源）。

密钥只从本机私密入口读取，绝不写进：
  - 技能正文、README、可分享安装包
  - 日志、稿件目录、gpt_meta.json
  - 命令行参数以外的任何共享位置

读取顺序（先到先用）：
  1. config["api_key"]（来自私密文件）
  2. 环境变量 config["api_key_env"]，默认 XHS_GPT_API_KEY
"""
from __future__ import annotations

import json
import os
from pathlib import Path

def _default_root() -> Path:
    """安装根：优先环境变量 XHSWORK_ROOT，否则由本文件位置推导（<根>\tools\gpt-writer\gptw）。"""
    env = os.environ.get("XHSWORK_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config").is_dir() or (parent / "tools").is_dir():
            return parent
    return Path(r"D:\XHSWork")


XHS_ROOT = _default_root()
# 主人填写密钥的本地私密文件（不随技能分发）
LOCAL_SECRET_FILE = XHS_ROOT / "config" / "gpt.local.json"
# 不含任何密钥的模板，可以随技能/安装包分发
TEMPLATE_FILE = XHS_ROOT / "tools" / "gpt-writer" / "config.example.json"

DEFAULTS = {
    "provider": "openai",
    # responses = OpenAI Responses API（官方首选）
    # chat_completions = 多数兼容服务商使用的 /chat/completions
    "protocol": "responses",
    "base_url": "https://api.openai.com/v1",
    "model": "",
    "api_key": "",
    "api_key_env": "XHS_GPT_API_KEY",
    # json_schema | json_object | none（服务商不支持结构化输出时用 none，靠提示词约束）
    "json_mode": "json_schema",
    # 留空自动：responses→max_output_tokens，chat_completions→max_tokens
    "max_tokens_param": "",
    "limits": {
        "max_input_chars": 24000,
        "max_output_tokens": 3500,
        "max_retries": 2,
        "timeout_seconds": 240,
        "backoff_seconds": 3,
    },
}

PROTOCOLS = ("responses", "chat_completions")
JSON_MODES = ("json_schema", "json_object", "none")


class ConfigError(RuntimeError):
    pass


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | None = None) -> dict:
    target = Path(path) if path else LOCAL_SECRET_FILE
    raw = {}
    source = "defaults"
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise ConfigError("配置文件不是合法 JSON：%s（%s）" % (target, exc))
        source = str(target)
    cfg = _merge(DEFAULTS, raw)
    cfg["_source"] = source
    cfg["_secret_file"] = str(LOCAL_SECRET_FILE)
    cfg["_template_file"] = str(TEMPLATE_FILE)
    return cfg


def validate_config(cfg: dict) -> list[str]:
    """返回配置层面的问题列表（不含网络连通性）。"""
    problems = []
    protocol = str(cfg.get("protocol") or "").lower()
    if protocol not in PROTOCOLS:
        problems.append("protocol 只能是 %s，当前为 %r" % (" / ".join(PROTOCOLS), cfg.get("protocol")))
    if not str(cfg.get("model") or "").strip():
        problems.append("model 未填写（填服务商实际模型 ID，例如 gpt-5 或 gpt-4.1）")
    base = str(cfg.get("base_url") or "").strip()
    if not base.startswith(("http://", "https://")):
        problems.append("base_url 必须以 http(s):// 开头，当前为 %r" % base)
    mode = str(cfg.get("json_mode") or "").lower()
    if mode not in JSON_MODES:
        problems.append("json_mode 只能是 %s，当前为 %r" % (" / ".join(JSON_MODES), cfg.get("json_mode")))
    if not resolve_api_key(cfg):
        problems.append(
            "api_key 未填写：在 %s 的 \"api_key\" 字段填入，或设置环境变量 %s"
            % (active_secret_file(cfg), cfg.get("api_key_env") or "XHS_GPT_API_KEY")
        )
    limits = cfg.get("limits") or {}
    for key, low in (("max_output_tokens", 200), ("max_retries", 0), ("timeout_seconds", 10)):
        value = limits.get(key)
        if not isinstance(value, int) or value < low:
            problems.append("limits.%s 应为不小于 %d 的整数，当前为 %r" % (key, low, value))
    return problems


def active_secret_file(cfg: dict) -> str:
    """本次实际生效的私密配置文件（多套服务商配置时，提示要指向真正在用的那个）。"""
    src = str(cfg.get("_source") or "").strip()
    if src and src != "defaults":
        return src
    return str(LOCAL_SECRET_FILE)


def resolve_api_key(cfg: dict) -> str:
    key = str(cfg.get("api_key") or "").strip()
    if key:
        return key
    env_name = str(cfg.get("api_key_env") or "XHS_GPT_API_KEY").strip()
    if env_name:
        return str(os.environ.get(env_name) or "").strip()
    return ""


def mask_key(key: str) -> str:
    if not key:
        return "(未配置)"
    if len(key) <= 8:
        return "*" * len(key)
    return "%s...%s（长度 %d）" % (key[:4], key[-4:], len(key))
