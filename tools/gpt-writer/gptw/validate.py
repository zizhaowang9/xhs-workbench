# -*- coding: utf-8 -*-
"""输出结构定义与本地校验（不联网也能跑）。

校验分两级：
  error   —— 现有渲染/填稿工具会读不了或明显违规，必须让 GPT 重来
  warning —— 能落盘但建议人工看一眼（字数偏移、疑似承诺用语等）
"""
from __future__ import annotations

import json
import re

_COVER = {
    "type": "object",
    "additionalProperties": False,
    "required": ["emoji", "title", "subtitle"],
    "properties": {
        "emoji": {"type": "string"},
        "title": {"type": "string", "description": "封面主标题，最多 5 个汉字（渲染器按 151px 排版，超过 5 字必然折行）"},
        "subtitle": {"type": "string", "description": "封面副标题，最多 10 个汉字（72px 一行上限）"},
    },
}

_CARD = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text"],
    "properties": {"text": {"type": "string"}},
}

_VIDEO = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outline", "script"],
    "properties": {
        "outline": {"type": "array", "items": {"type": "string"}},
        "script": {"type": "string"},
    },
}

_BASE_PROPS = {
    "title": {"type": "string"},
    "content": {"type": "string"},
    "tags": {"type": "array", "items": {"type": "string"}},
    "cover": _COVER,
    "cards": {"type": "array", "items": _CARD},
    "risk_notes": {"type": "array", "items": {"type": "string"}},
}


def schema_for(video: bool = False) -> dict:
    props = dict(_BASE_PROPS)
    required = ["title", "content", "tags", "cover", "cards", "risk_notes"]
    if video:
        props["video"] = _VIDEO
        required.append("video")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": props,
    }


SCHEMA = schema_for(False)

PROMISE_WORDS = ["保证", "一定能", "必然", "稳赚", "包教", "收入翻倍", "躺着赚", "百分之百", "绝对有效"]


def extract_json(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("返回为空")
    fence = re.match(r"(?s)^```[a-zA-Z]*\s*(.*?)\s*```$", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
    except ValueError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("返回里找不到 JSON 对象：%s" % raw[:200])
        data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层不是对象")
    return data


def nonblank_len(text: str) -> int:
    return len(re.sub(r"\s", "", text or ""))


def _looks_like_promise(sentence: str) -> bool:
    for word in PROMISE_WORDS:
        pos = sentence.find(word)
        if pos < 0:
            continue
        prefix = sentence[max(0, pos - 3) : pos]
        if "不" in prefix or "没" in prefix:
            continue
        return True
    return False


def check(draft: dict, *, video: bool = False) -> tuple[list[str], list[str]]:
    errors, warnings = [], []

    title = str(draft.get("title") or "").strip()
    if not title:
        errors.append("title 为空")
    elif len(title) > 20:
        errors.append("title 长度 %d 超过小红书 20 字上限" % len(title))
    elif len(title) < 8:
        warnings.append("title 只有 %d 字，钩子可能偏弱" % len(title))

    content = str(draft.get("content") or "").strip()
    count = nonblank_len(content)
    if count < 150:
        errors.append("正文只有 %d 个非空白字，过短" % count)
    elif count > 460:
        errors.append("正文 %d 个非空白字，超过 460 上限" % count)
    elif count < 200 or count > 400:
        warnings.append("正文 %d 个非空白字，超出建议的 200-400 区间" % count)
    if "#" in content:
        errors.append("正文里出现 #，话题应只放在 tags 字段")
    if len([line for line in content.splitlines() if line.strip()]) < 3:
        warnings.append("正文分段少于 3 段，阅读节奏偏挤")

    tags = draft.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append("tags 缺失或不是数组")
        tags = []
    clean_tags = []
    for tag in tags:
        value = str(tag).strip().lstrip("#").strip()
        if not value:
            continue
        if re.search(r"\s", value):
            errors.append("话题「%s」含空格，会被拆成多个标签" % value)
        if len(value) > 14:
            warnings.append("话题「%s」偏长" % value)
        if value not in clean_tags:
            clean_tags.append(value)
    if len(clean_tags) < 5:
        errors.append("有效话题只有 %d 个，建议 5-8 个" % len(clean_tags))
    if len(clean_tags) > 10:
        errors.append("有效话题 %d 个，超过小红书 10 个上限" % len(clean_tags))

    cover = draft.get("cover") or {}
    if not isinstance(cover, dict):
        errors.append("cover 不是对象")
        cover = {}
    for key in ("emoji", "title", "subtitle"):
        if not str(cover.get(key) or "").strip():
            errors.append("cover.%s 为空" % key)
    cover_title = str(cover.get("title") or "").strip()
    cover_sub = str(cover.get("subtitle") or "").strip()
    title_n = nonblank_len(cover_title)
    sub_n = nonblank_len(cover_sub)
    if title_n > 5:
        errors.append("封面主标题 %d 字，1080 宽一行只放得下 5 字，会断行（实测 6 字折成 5+1）" % title_n)
    if sub_n > 10:
        errors.append("封面副标题 %d 字，1080 宽一行放得下 10 字，会断行" % sub_n)

    cards = draft.get("cards")
    if not isinstance(cards, list):
        errors.append("cards 不是数组")
        cards = []
    if len(cards) != 5:
        errors.append("cards 应为 5 张正文卡，实际 %d 张" % len(cards))
    for index, card in enumerate(cards, start=1):
        text = str((card or {}).get("text") or "").strip()
        if not text:
            errors.append("第 %d 张卡片没有文案" % index)
            continue
        size = nonblank_len(text)
        if size < 20:
            errors.append("第 %d 张卡片只有 %d 字，太单薄" % (index, size))
        elif size > 260:
            warnings.append("第 %d 张卡片 %d 字，可能溢出，建议压到 140 字以内" % (index, size))
        elif size > 160:
            warnings.append("第 %d 张卡片 %d 字，偏多" % (index, size))

    risk = draft.get("risk_notes")
    if risk is not None and not isinstance(risk, list):
        warnings.append("risk_notes 不是数组，已忽略")

    if video:
        block = draft.get("video") or {}
        if not isinstance(block, dict):
            errors.append("video 不是对象")
        else:
            outline = block.get("outline") or []
            script = str(block.get("script") or "").strip()
            if not isinstance(outline, list) or len(outline) < 3:
                errors.append("video.outline 少于 3 条")
            if nonblank_len(script) < 200:
                errors.append("video.script 过短（%d 字）" % nonblank_len(script))

    pieces = [content, str(cover.get("title") or ""), str(cover.get("subtitle") or "")]
    pieces += [str((card or {}).get("text") or "") for card in cards if isinstance(card, dict)]
    for piece in pieces:
        for sentence in re.split(r"[。！？\n]", piece):
            if _looks_like_promise(sentence):
                warnings.append("疑似承诺用语：%s" % sentence.strip()[:40])
                break

    return errors, warnings
