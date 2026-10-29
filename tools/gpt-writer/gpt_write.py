#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 写稿工具（xhs-daily 专用，只写本地文件，不碰桥、不碰草稿）。

用法：
  # 1) 只检查配置和材料（不发请求）
  python gpt_write.py --check
  python gpt_write.py --task task.json --run-dir <dir> --check

  # 2) 正式写稿（缺密钥时会直接 blocked，不会伪造结果）
  python gpt_write.py --task task.json --run-dir <dir>

  # 3) 本地格式自查（明确标 mock，不可当成 GPT 返回）
  python gpt_write.py --task task.json --run-dir <dir> --mock

产物：title.txt / content.txt / cards.md / draft.gpt.json / gpt_meta.json（+ video.md）
退出码：0 成功或复用；2 配置不完整；3 材料或输出校验失败；4 调用失败
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from gptw import config as cfgmod  # noqa: E402
from gptw import emit, materials as matmod, mockdata, providers, trace as tracemod, validate  # noqa: E402

USAGE_LOG = cfgmod.XHS_ROOT / "config" / "gpt_usage.jsonl"

GUIDE_FIELDS = [
    "provider：填服务商名（仅作记录，如 openai / azure-openai / 其他）",
    "protocol：官方 OpenAI 用 responses；其他服务商按其文档填 chat_completions",
    "base_url：该服务商的 API 根地址，含版本段，如 https://api.openai.com/v1",
    "model：该服务商实际模型 ID，如 gpt-5、gpt-4.1",
    "api_key：该服务商的密钥（只写在这个本地文件里，别贴到聊天里）",
    "limits：max_output_tokens / max_retries 可按需调，默认 3500 / 2",
]


def stamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def finish(run_dir: Path | None, result: dict, code: int) -> int:
    result["finished_at"] = stamp()
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if run_dir:
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "gpt_result.json").write_text(body, encoding="utf-8", newline="\n")
        except OSError as exc:
            safe_print("WARN cannot write gpt_result.json: %s" % exc)
    safe_print("STATUS=%s" % result.get("status"))
    if result.get("run_dir"):
        safe_print("RUN_DIR=%s" % result["run_dir"])
    if result.get("message"):
        safe_print("MESSAGE=%s" % result["message"])
    if result.get("validation"):
        safe_print("VALID=%s errors=%d warnings=%d" % (
            result["validation"].get("valid"),
            len(result["validation"].get("errors") or []),
            len(result["validation"].get("warnings") or []),
        ))
    return code


def safe_print(text: str) -> None:
    try:
        print(text)
    except Exception:  # 控制台编码异常不影响主流程
        try:
            print(text.encode("ascii", "backslashreplace").decode("ascii"))
        except Exception:
            pass


def log_usage(record: dict) -> None:
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        safe_print("WARN usage log failed: %s" % exc)


def diff_draft(old: dict, new: dict) -> list[str]:
    """改稿模式用：看这次到底动了哪些字段，防止悄悄整篇重写。"""
    changed = []
    if str(old.get("title") or "") != str(new.get("title") or ""):
        changed.append("title")
    if str(old.get("content") or "") != str(new.get("content") or ""):
        changed.append("content")
    if list(old.get("tags") or []) != list(new.get("tags") or []):
        changed.append("tags")
    if (old.get("cover") or {}) != (new.get("cover") or {}):
        changed.append("cover")
    old_cards = [str((card or {}).get("text") or "") for card in (old.get("cards") or [])]
    new_cards = [str((card or {}).get("text") or "") for card in (new.get("cards") or [])]
    if old_cards != new_cards:
        marks = []
        for index in range(max(len(old_cards), len(new_cards))):
            before = old_cards[index] if index < len(old_cards) else None
            after = new_cards[index] if index < len(new_cards) else None
            if before != after:
                marks.append(str(index + 1))
        changed.append("cards[%s]" % ",".join(marks))
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GPT 写稿：接收本篇任务，调用 GPT，落成现有工具可读的文件")
    parser.add_argument("--task", help="任务 JSON 路径")
    parser.add_argument("--run-dir", help="本篇目录（产物写到 <run-dir> 根下）")
    parser.add_argument("--config", help="配置文件路径，默认 <安装根>\\config\\gpt.local.json（可用 --config 指向自己的私密配置）")
    parser.add_argument("--mock", action="store_true", help="用本地样例跑通格式链路（不请求网络，结果标 mock）")
    parser.add_argument("--force", action="store_true", help="已有成功稿件也重新调用 GPT")
    parser.add_argument("--check", action="store_true", help="只检查配置与材料，不发起调用")
    parser.add_argument("--video", action="store_true", help="同时要页面要点与讲稿（需视频能力已安装）")
    parser.add_argument("--example-limit", type=int, default=1, help="附带的历史文案示例篇数，默认 1")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir) if args.run_dir else None
    result = {"status": "unknown", "started_at": stamp(), "run_dir": str(run_dir) if run_dir else ""}

    # ---- 配置 ----
    try:
        cfg = cfgmod.load_config(args.config)
    except cfgmod.ConfigError as exc:
        result.update(status="config_error", message=str(exc))
        return finish(run_dir, result, 2)

    api_key = cfgmod.resolve_api_key(cfg)
    cfg["api_key_value"] = api_key
    problems = cfgmod.validate_config(cfg)
    result["config"] = {
        "source": cfg["_source"],
        "provider": cfg.get("provider"),
        "protocol": cfg.get("protocol"),
        "base_url": cfg.get("base_url"),
        "model": cfg.get("model"),
        "json_mode": cfg.get("json_mode"),
        "api_key": cfgmod.mask_key(api_key),
        "limits": cfg.get("limits"),
        "secret_file": cfgmod.active_secret_file(cfg),
    }

    if problems and not args.mock:
        result.update(
            status="blocked",
            message="配置不完整，未发起调用（也不会改用本机模型代写）",
            problems=problems,
            guide={"secret_file": cfgmod.active_secret_file(cfg), "fields": GUIDE_FIELDS},
        )
        return finish(run_dir, result, 2)

    # ---- 材料 ----
    if args.check and not args.task:
        result.update(status="config_ok" if not problems else "config_pending", problems=problems,
                      message="仅检查配置；带上 --task 可同时检查材料")
        return finish(run_dir, result, 0 if not problems or args.mock else 2)

    if not args.task:
        result.update(status="task_error", message="缺少 --task")
        return finish(run_dir, result, 3)

    try:
        task = matmod.load_task(args.task)
    except Exception as exc:
        result.update(status="task_error", message="任务文件读不了：%s" % exc)
        return finish(run_dir, result, 3)

    budget = max(8000, int(cfg["limits"]["max_input_chars"]) - 1200)
    bundle = matmod.build(task, example_limit=max(0, args.example_limit), run_dir=run_dir,
                          video=args.video, budget=budget)
    system_prompt = bundle["system"]
    user_prompt = bundle["user"]
    stats = dict(bundle["stats"])

    max_chars = int(cfg["limits"]["max_input_chars"])
    total_chars = len(system_prompt) + len(user_prompt)
    if total_chars > max_chars:
        room = max(2000, max_chars - len(system_prompt) - 100)
        user_prompt = user_prompt[:room]
        stats["truncated"] = True
        stats["truncated_from"] = total_chars
    stats["input_chars"] = len(system_prompt) + len(user_prompt)
    result["materials"] = stats
    if run_dir:
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
            rec = dict(bundle.get("record") or {})
            rec["built_at"] = stamp()
            rec["task_file"] = str(args.task)
            rec["stats"] = stats
            (run_dir / "materials_used.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        except OSError as exc:
            safe_print("WARN cannot write materials_used.json: %s" % exc)

    if args.check:
        result.update(status="materials_ok", problems=problems,
                      message="配置与材料检查完成，未调用 GPT")
        if run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "prompt.preview.md").write_text(
                "# SYSTEM\n\n%s\n\n# USER\n\n%s\n" % (system_prompt, user_prompt),
                encoding="utf-8", newline="\n",
            )
        return finish(run_dir, result, 0)

    # ---- 幂等：已有成功稿件就复用 ----
    if run_dir and not args.force and not args.mock:
        meta_file = run_dir / "gpt_meta.json"
        draft_file = run_dir / "draft.gpt.json"
        if meta_file.exists() and draft_file.exists():
            try:
                old = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            except ValueError:
                old = {}
            if old.get("valid") and old.get("real_call") and old.get("trace_ok", True):
                result.update(status="reused", message="已有成功稿件，直接复用，未再次调用 GPT",
                              meta=old)
                return finish(run_dir, result, 0)

    schema = validate.schema_for(args.video)
    meta = {
        "provider": cfg.get("provider"),
        "protocol": cfg.get("protocol"),
        "base_url_host": emit.base_host(str(cfg.get("base_url") or "")),
        "model_requested": cfg.get("model"),
        "model_returned": "",
        "usage": {},
        "attempts": 0,
        "degraded": [],
        "started_at": stamp(),
        "input_chars": stats["input_chars"],
        "materials": stats,
        "task_file": str(args.task),
    }

    # ---- 调用 ----
    if args.mock:
        draft = json.loads(json.dumps(mockdata.MOCK_DRAFT, ensure_ascii=False))
        if args.video:
            draft["video"] = json.loads(json.dumps(mockdata.MOCK_VIDEO, ensure_ascii=False))
        meta.update(mode="mock", real_call=False, protocol="mock", model_returned="mock",
                    usage={"input_tokens": None, "output_tokens": None, "total_tokens": None},
                    mock_reason="本地样例，仅用于格式自查，不是 GPT 返回")
    else:
        try:
            generated = providers.generate(cfg, system_prompt, user_prompt, schema)
        except providers.ProviderError as exc:
            meta.update(mode="failed", real_call=False, attempted=True, error=str(exc),
                        attempts=getattr(exc, "attempts", 0),
                        error_status=getattr(exc, "status", None),
                        error_body=(getattr(exc, "body", "") or "")[:800])
            if run_dir:
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "gpt_meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            hint = ""
            if any(k in (str(exc) + (getattr(exc, "body", "") or "")) for k in ("insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached")):
                hint = "%s 账户余额/额度不足：到该服务商控制台充值或加额度后，用同一条命令重跑即可，不用改模型或地址" % (cfg.get("provider") or "服务商")
            result.update(status="call_failed", message="GPT 调用失败，进度已保留；未改用其它模型写稿",
                          error=str(exc), hint=hint, meta=meta)
            return finish(run_dir, result, 4)

        meta.update(mode="real", real_call=True, protocol=generated["protocol"],
                    model_returned=generated["model_returned"],
                    usage=generated["usage"], attempts=generated["attempts"],
                    degraded=generated["degraded"], latency_seconds=generated["elapsed_seconds"],
                    response_id=generated["raw_id"])

        try:
            draft = validate.extract_json(generated["text"])
        except ValueError as exc:
            if run_dir:
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "draft.gpt.raw.txt").write_text(generated["text"], encoding="utf-8", newline="\n")
            meta.update(valid=False, errors=["返回不是合法 JSON：%s" % exc])
            if run_dir:
                (run_dir / "gpt_meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            result.update(status="invalid", message="GPT 返回的 JSON 解析失败，原始文本已存 draft.gpt.raw.txt",
                          meta=meta)
            return finish(run_dir, result, 3)

    # ---- 校验 ----
    errors, warnings = validate.check(draft, video=args.video)
    revise, _revise_problems = matmod.load_revise(task)
    revise_meta = {}
    if revise:
        changed = diff_draft(revise["data"], draft)
        revise_meta = {
            "source": revise["source"],
            "notes": revise["notes"],
            "changed_fields": changed,
        }
        if not changed:
            warnings.append("改稿结果与原稿完全一致，可能修改意见没生效")
    meta.update(valid=not errors, errors=errors, warnings=warnings,
                risk_notes=draft.get("risk_notes") or [],
                finished_at=stamp(),
                body_chars=validate.nonblank_len(str(draft.get("content") or "")))
    if revise_meta:
        meta["revise"] = revise_meta
    result["validation"] = {"valid": not errors, "errors": errors, "warnings": warnings}

    if errors:
        if run_dir:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "draft.gpt.json").write_text(
                json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            (run_dir / "gpt_meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        result.update(status="invalid", message="输出未通过格式校验，未生成 title/content/cards（避免半成品）",
                      meta=meta)
        return finish(run_dir, result, 3)

    if not run_dir:
        result.update(status="no_run_dir", message="校验通过但缺少 --run-dir，无法落盘", meta=meta)
        return finish(None, result, 3)

    report = tracemod.check(draft, stats, source_text=user_prompt)
    meta.update(trace_ok=not report["blocking"], trace=report)
    if report["warnings"]:
        warnings.extend(["溯源：" + w for w in report["warnings"]])
    if report["errors"]:
        errors.extend(["溯源：" + e for e in report["errors"]])
    meta["valid"] = not errors
    result["validation"] = {"valid": not errors, "errors": errors, "warnings": warnings}
    result["trace"] = report
    try:
        (run_dir / "trace_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    except OSError as exc:
        safe_print("WARN cannot write trace_report.json: %s" % exc)
    written = emit.write_outputs(run_dir, draft, meta, video=args.video)
    if meta.get("real_call"):
        log_usage({
            "at": stamp(),
            "provider": meta.get("provider"),
            "protocol": meta.get("protocol"),
            "base_url_host": meta.get("base_url_host"),
            "model_requested": meta.get("model_requested"),
            "model_returned": meta.get("model_returned"),
            "usage": meta.get("usage"),
            "run_dir": str(run_dir),
            "title": draft.get("title"),
        })

    if report["blocking"]:
        result.update(status="trace_failed",
                      message="内容与知识库来源对不上，已写出文件但需人工处理",
                      outputs=written, meta=meta)
        return finish(run_dir, result, 3)
    result.update(status="ok", message="已生成 title.txt / content.txt / cards.md", outputs=written, meta=meta)
    return finish(run_dir, result, 0)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        safe_print("FATAL traceback written to stderr")
        traceback.print_exc()
        sys.exit(1)
