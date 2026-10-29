# -*- coding: utf-8 -*-
"""生成后的溯源核对。

不是格式校验（那个在 validate.py），而是回答一个问题：
“这篇稿子说的东西，能不能对上这次真正给它的材料？”

注意：本模块通过不代表结论一定有依据。关键词覆盖率、trace_ok 都只是信号，
最终依据要回到 knowledge/04-案例与训练/05-依据核验表.md 逐条对原文。

检查项：
1. 红线：知识库里没有公会政策/分成/保底/扶持，出现即报错。
2. 红线：不得把自己编的对话写成第一人称真实案例（“我带过的主播…”）。
3. 红线：声称“真实案例/真人真事”但没有主人提供的案例时不得写。
4. 提示：正文/卡片里残留来源编号（“素材 10”）要删掉。
5. 提示：示范对话没有标“示例”。
6. 提示：提供的知识条目有没有被用上（覆盖率）。
7. 提示：出现“资料里提到/资料里说”时，本篇是否真的给了素材依据。
8. 提示：量化表述（秒数/分钟/比例/轮次）在材料里找不到对应数字——多半是自己造的阈值。
9. 提示：绝对化要求（“每个进场的人都…”“唯一”）材料未必支持。
"""
from __future__ import annotations

import re

POLICY_WORDS = [
    "分成比例", "五五分成", "四六分成", "保底", "底薪", "入驻条件", "扶持政策",
    "推荐位", "公会分成", "签约金", "结算周期", "退会", "违约金",
]
FAKE_CASE = [
    "我带过的", "我带的主播", "我的学员", "我有个学员", "我之前带", "我带的徒弟",
    "我团队里的主播", "我手上有个主播", "我辅导过",
]
REAL_CASE = ["真实案例", "真人真事", "真实经历", "我认识的一个主播", "身边有个主播"]
QUOTE = re.compile(r"[“\"「][^”\"」]{6,}[”\"」]")
CLAIM = re.compile(r"^.{0,40}(要|别|不要|先|必须|关键|核心|记住|就是|只能|一定).{0,60}$")
NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(秒|分钟|小时|天|周|个月|月|%|成|轮|次)")
ASSERTIVE = ["每个进场的人", "每一个人都", "每个人都要", "所有人都要", "必须人人", "唯一", "百分百"]


def _all_text(draft: dict) -> str:
    parts = [str(draft.get("title") or ""), str(draft.get("content") or "")]
    cover = draft.get("cover") or {}
    parts += [str(cover.get("title") or ""), str(cover.get("subtitle") or ""), str(cover.get("emoji") or "")]
    for card in draft.get("cards") or []:
        parts.append(str((card or {}).get("text") or ""))
    parts += [str(x) for x in (draft.get("tags") or [])]
    return "\n".join(parts)


def _grams(text: str) -> set[str]:
    clean = re.sub(r"[\s，。、？！：；“”‘’（）()\[\]【】,.!?:;\"'-]+", "", text)
    return {clean[i:i + 2] for i in range(len(clean) - 1)} if len(clean) > 1 else set()


def numeric_check(text: str, source: str) -> dict:
    """量化表述是否能在本次材料里找到对应数字。找不到的列出来，交人工判断。"""
    src = source or ""
    supported, unsupported = [], []
    for m in NUM.finditer(text):
        raw, num, unit = m.group(0), m.group(1), m.group(2)
        hit = raw in src or (num + unit) in src or re.search(num + r"\s*" + re.escape(unit), src)
        (supported if hit else unsupported).append(raw)
    return {"supported": sorted(set(supported)), "unsupported": sorted(set(unsupported)),
            "source_checked": bool(src)}


def check(draft: dict, stats: dict, source_text: str = "") -> dict:
    text = _all_text(draft)
    errors, warnings = [], []

    for word in POLICY_WORDS:
        if word in text:
            errors.append("出现资料中没有的公会政策表述「%s」——知识库无任何可核实政策，必须删除" % word)

    for phrase in FAKE_CASE:
        if phrase in text:
            errors.append("出现第一人称案例「%s」——知识库没有已确认的真实带教案例，不能这样写" % phrase)

    for phrase in REAL_CASE:
        if phrase in text:
            errors.append("声称真实案例「%s」——主人尚未提供可对外案例，改写为「示例」或删掉" % phrase)

    if re.search(r"素材\s*[0-9]+", text):
        warnings.append("正文或卡片里残留来源编号（如「素材 10」），对外发布前要删掉")

    provided_mats = set(str(x) for x in (stats.get("materials") or []))
    quoted = QUOTE.findall(text)
    if quoted and "示例" not in text:
        warnings.append("出现 %d 处引号对话但没有标注「示例」" % len(quoted))

    if ("资料里提到" in text or "资料里说" in text or "资料中提到" in text) and not provided_mats:
        warnings.append("写了「资料里提到」，但本篇没有给任何素材依据")

    nums = numeric_check(text, source_text)
    if nums["unsupported"]:
        warnings.append("这些量化表述在本次材料里找不到对应数字，可能是自己造的阈值：%s"
                        % "、".join(nums["unsupported"]))

    hits = [w for w in ASSERTIVE if w in text]
    if hits:
        warnings.append("出现绝对化要求「%s」，确认材料是否支持；不支持的改为方法或建议" % "、".join(hits))

    coverage = []
    draft_grams = _grams(text)
    for item in (stats.get("knowledge_list") or []):
        title = str(item.get("title") or "")
        g = _grams(title)
        hit = len(g & draft_grams) / max(1, len(g))
        coverage.append({"id": item.get("id"), "title": title, "overlap": round(hit, 2)})
    unused = [c["id"] for c in coverage if c["overlap"] < 0.15]
    if unused:
        warnings.append("这些知识条目基本没被用上：%s（确认不是定位错了）" % "、".join(unused))

    claims = [line.strip() for line in str(draft.get("content") or "").splitlines() if CLAIM.match(line.strip())]
    return {
        "ok": not errors,
        "blocking": bool(errors),
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "claims_count": len(claims),
        "numeric": nums,
        "provided_materials": sorted(provided_mats),
        "provided_knowledge": list(stats.get("knowledge") or []),
        "examples_used": list(stats.get("examples") or []),
        "note": "trace_ok 只代表没有触发红线和绝对化硬检查，不代表每条结论都有据；依据以 knowledge/04-案例与训练/05-依据核验表.md 为准。",
    }
