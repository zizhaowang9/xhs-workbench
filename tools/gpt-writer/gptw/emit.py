# -*- coding: utf-8 -*-
"""把 GPT 的 JSON 结果落成现有渲染 / 填稿工具直接能读的文件。

产物（与手工写稿时完全一致，现有工具无需修改）：
  title.txt    一行标题
  content.txt  正文 + 空行 + 空格分隔的话题行
  cards.md     YAML frontmatter + 5 页正文（--- 分隔），供 render_xhs.py 出图
  draft.gpt.json  GPT 原始结构（追溯用，不参与渲染）
  gpt_meta.json   服务商 / 模型 / 用量 / 校验结论（不含密钥）
  video.md     仅启用视频能力时生成
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


def _write(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8", newline="\n")
    return path.name


def _yaml_str(value: str) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def render_cards_md(draft: dict) -> str:
    cover = draft.get("cover") or {}
    lines = [
        "---",
        "emoji: %s" % _yaml_str(cover.get("emoji")),
        "title: %s" % _yaml_str(cover.get("title")),
        "subtitle: %s" % _yaml_str(cover.get("subtitle")),
        "---",
        "",
    ]
    body_parts = []
    for card in draft.get("cards") or []:
        text = str((card or {}).get("text") or "").strip()
        if text:
            body_parts.append(text)
    lines.append("\n\n---\n\n".join(body_parts))
    lines.append("")
    return "\n".join(lines)


def render_content_txt(draft: dict) -> str:
    body = str(draft.get("content") or "").strip()
    tags = []
    for tag in draft.get("tags") or []:
        value = str(tag).strip().lstrip("#").strip()
        if value and value not in tags:
            tags.append(value)
    tag_line = " ".join("#" + value for value in tags)
    return "%s\n\n%s\n" % (body, tag_line)


def render_video_md(draft: dict) -> str:
    block = draft.get("video") or {}
    outline = [str(item).strip() for item in (block.get("outline") or []) if str(item).strip()]
    script = str(block.get("script") or "").strip()
    lines = ["# 页面要点", ""]
    lines += ["%d. %s" % (i, item) for i, item in enumerate(outline, start=1)]
    lines += ["", "# 讲稿", "", script, ""]
    return "\n".join(lines)


def write_outputs(run_dir: Path, draft: dict, meta: dict, *, video: bool = False) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    written = {}

    written["draft.gpt.json"] = _write(
        run_dir / "draft.gpt.json", json.dumps(draft, ensure_ascii=False, indent=2) + "\n"
    )
    written["title.txt"] = _write(run_dir / "title.txt", str(draft.get("title") or "").strip() + "\n")
    written["content.txt"] = _write(run_dir / "content.txt", render_content_txt(draft))
    written["cards.md"] = _write(run_dir / "cards.md", render_cards_md(draft))
    if video and draft.get("video"):
        written["video.md"] = _write(run_dir / "video.md", render_video_md(draft))

    payload = dict(meta)
    payload["outputs"] = list(written.values())
    _write(run_dir / "gpt_meta.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    written["gpt_meta.json"] = "gpt_meta.json"
    return written


def base_host(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except ValueError:
        return url
