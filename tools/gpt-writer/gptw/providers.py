# -*- coding: utf-8 -*-
"""GPT 调用层：Responses API 优先，Chat Completions 兼容。

只用标准库，不改变现有 Bridge / 渲染 / 发布链路的依赖。
每次调用都会带回 provider、协议、请求模型、返回模型、token 用量与降级记录，
用来证明"这篇确实是 GPT 写的"，也方便核对用量。

重要：不同服务商只用自己的一套 base_url + 密钥，绝不跨服务商混用。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    def __init__(self, message, *, status=None, body="", retryable=False, attempts=0):
        super().__init__(message)
        self.status = status
        self.body = body or ""
        self.retryable = retryable
        self.attempts = attempts


def _join(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def _post(url: str, api_key: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Bearer " + api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        # 余额/额度类 429 重试没有意义，直接定性为不可重试，避免白白多发请求
        quota_hit = any(
            mark in detail
            for mark in ("insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached")
        )
        message = "HTTP %s" % exc.code
        if quota_hit:
            message = "HTTP %s 账户余额/额度不足（insufficient_quota），不是接口或模型不可用" % exc.code
        raise ProviderError(
            message,
            status=exc.code,
            body=detail[:2000],
            retryable=(not quota_hit) and exc.code in (408, 409, 425, 429, 500, 502, 503, 504),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError("网络错误：%s" % exc, retryable=True)
    try:
        return json.loads(raw)
    except ValueError:
        raise ProviderError("返回不是合法 JSON", body=raw[:2000], retryable=False)


def _usage(resp: dict) -> dict:
    usage = resp.get("usage") or {}
    inp = usage.get("input_tokens", usage.get("prompt_tokens"))
    outp = usage.get("output_tokens", usage.get("completion_tokens"))
    total = usage.get("total_tokens")
    if total is None and (inp is not None or outp is not None):
        total = (inp or 0) + (outp or 0)
    return {"input_tokens": inp, "output_tokens": outp, "total_tokens": total}


def _responses_text(resp: dict) -> str:
    if isinstance(resp.get("output_text"), str) and resp["output_text"].strip():
        return resp["output_text"]
    parts = []
    for item in resp.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in (None, "message"):
            continue
        for chunk in item.get("content") or []:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") not in (None, "output_text", "text"):
                continue
            if isinstance(chunk.get("text"), str):
                parts.append(chunk["text"])
    return "".join(parts)


def _format_block(cfg: dict, schema: dict) -> dict:
    mode = str(cfg.get("json_mode") or "json_schema").lower()
    if mode == "json_schema":
        return {"type": "json_schema", "name": "xhs_article", "schema": schema, "strict": True}
    if mode == "json_object":
        return {"type": "json_object"}
    return {}


def _call_responses(cfg, system, user, schema, max_out):
    url = _join(cfg["base_url"], "responses")
    payload = {
        "model": cfg["model"],
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": user}]},
        ],
        "max_output_tokens": max_out,
    }
    fmt = _format_block(cfg, schema)
    if fmt:
        payload["text"] = {"format": fmt}

    degraded = []
    timeout = int(cfg["limits"]["timeout_seconds"])
    try:
        resp = _post(url, cfg["api_key_value"], payload, timeout)
    except ProviderError as exc:
        if exc.status != 400:
            raise
        # 逐项降级：先退结构化输出，再退角色数组，最后仍失败就原样报错（可能是模型/地址填错）
        if "text" in payload:
            degraded.append("该服务商不接受 text.format，已去掉结构化输出约束")
            payload.pop("text", None)
            try:
                resp = _post(url, cfg["api_key_value"], payload, timeout)
            except ProviderError as exc2:
                if exc2.status != 400:
                    raise
                degraded.append("input 角色数组不被接受，已改为纯文本输入")
                payload.pop("input", None)
                payload["input"] = system + "\n\n" + user
                resp = _post(url, cfg["api_key_value"], payload, timeout)
        else:
            degraded.append("input 角色数组不被接受，已改为纯文本输入")
            payload.pop("input", None)
            payload["input"] = system + "\n\n" + user
            resp = _post(url, cfg["api_key_value"], payload, timeout)

    if resp.get("status") == "incomplete":
        reason = (resp.get("incomplete_details") or {}).get("reason")
        raise ProviderError(
            "输出被截断（reason=%s）：请提高 limits.max_output_tokens 或压缩材料" % reason
        )
    text = _responses_text(resp)
    if not text.strip():
        raise ProviderError("Responses 返回空内容", body=json.dumps(resp, ensure_ascii=False)[:1500])
    return text, resp, degraded


def _chat_content(resp: dict) -> str:
    choices = resp.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _call_chat(cfg, system, user, schema, max_out):
    url = _join(cfg["base_url"], "chat/completions")
    param = str(cfg.get("max_tokens_param") or "").strip() or "max_tokens"
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        param: max_out,
    }
    fmt = _format_block(cfg, schema)
    if fmt:
        if fmt.get("type") == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "xhs_article", "schema": schema, "strict": True},
            }
        else:
            payload["response_format"] = fmt

    degraded = []
    timeout = int(cfg["limits"]["timeout_seconds"])
    try:
        resp = _post(url, cfg["api_key_value"], payload, timeout)
    except ProviderError as exc:
        if exc.status != 400 or "response_format" not in payload:
            raise
        degraded.append("该服务商不接受 json_schema，已退到 json_object")
        payload["response_format"] = {"type": "json_object"}
        try:
            resp = _post(url, cfg["api_key_value"], payload, timeout)
        except ProviderError as exc2:
            if exc2.status != 400:
                raise
            degraded.append("该服务商不接受 response_format，已去除约束")
            payload.pop("response_format", None)
            resp = _post(url, cfg["api_key_value"], payload, timeout)

    text = _chat_content(resp)
    if not text.strip():
        raise ProviderError("Chat Completions 返回空内容", body=json.dumps(resp, ensure_ascii=False)[:1500])
    return text, resp, degraded


def generate(cfg: dict, system: str, user: str, schema: dict, max_output_tokens: int | None = None) -> dict:
    """发起一次写稿调用，返回文本 + 追溯信息。失败按限额重试，重试耗尽后抛出。"""
    limits = cfg["limits"]
    max_out = int(max_output_tokens or limits["max_output_tokens"])
    protocol = str(cfg.get("protocol") or "responses").lower()
    attempts_allowed = int(limits["max_retries"]) + 1
    started = time.time()
    last_error = None
    attempts_used = 0

    for attempt in range(1, attempts_allowed + 1):
        attempts_used = attempt
        try:
            if protocol == "responses":
                text, resp, degraded = _call_responses(cfg, system, user, schema, max_out)
            else:
                text, resp, degraded = _call_chat(cfg, system, user, schema, max_out)
            return {
                "text": text,
                "protocol": protocol,
                "model_requested": cfg["model"],
                "model_returned": resp.get("model") or "",
                "usage": _usage(resp),
                "degraded": degraded,
                "attempts": attempt,
                "elapsed_seconds": round(time.time() - started, 2),
                "raw_id": resp.get("id") or "",
            }
        except ProviderError as exc:
            last_error = exc
            if not exc.retryable or attempt >= attempts_allowed:
                break
            time.sleep(float(limits["backoff_seconds"]) * attempt)

    extra = ""
    if last_error and last_error.body:
        extra = "｜返回片段：%s" % last_error.body[:400]
    raise ProviderError(
        "调用失败（尝试 %d 次）：%s%s" % (attempts_used, last_error, extra),
        status=getattr(last_error, "status", None),
        body=getattr(last_error, "body", ""),
        retryable=False,
        attempts=attempts_used,
    )
