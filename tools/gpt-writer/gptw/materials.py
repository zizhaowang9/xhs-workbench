# -*- coding: utf-8 -*-
"""组装给写稿模型的材料。

2026-10-29 起改为从运营知识库取材（`<安装根>\\knowledge`）：
1. 固定读业务总纲（定位 / 已确认事实 / 当前有效规则 / 表达标准）+ 当前任务进度，永不裁剪。
2. 先查知识目录定位条目（`03-运营知识`），再按条目的“依据”回 `02-原始资料` 取素材摘要，
   必要时从转写原文取相关片段（按关键词选窗口，不从头硬切）。
3. 写作范例走白名单（`config/style_examples.json`），只给主人明确认可的作品；
   mock / verify / 未审核的稿子不进入范例。
4. 材料超预算时按相关性从低到高舍弃（原文片段 → 素材摘要 → 知识条目），
   规则、输出要求、schema 永不截断。
5. 返回实际用料清单，供 gpt_write.py 落盘核对。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import knowledge as kb
from .config import XHS_ROOT
from .validate import SCHEMA

DEFAULT_SKILLS_DIR = XHS_ROOT / "skills"
RUNS_DIR = XHS_ROOT / "runs"

CAP_KNOWLEDGE = 1500
CAP_MATERIAL = 1800
CAP_EXCERPT = 1600
CAP_EXAMPLE = 700


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def skills_dir() -> Path:
    paths_file = XHS_ROOT / "config" / "paths.json"
    if paths_file.exists():
        try:
            data = json.loads(paths_file.read_text(encoding="utf-8-sig"))
            value = data.get("skills_dir")
            if value:
                return Path(value)
        except ValueError:
            pass
    return DEFAULT_SKILLS_DIR


def load_task(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for key in ("topic", "problem"):
        if not str(data.get(key) or "").strip():
            raise ValueError("任务文件缺少 %s" % key)
    data.setdefault("audience", "刚开播、缺方法的新人娱乐主播")
    data.setdefault("materials", [])
    data.setdefault("tags_hint", [])
    return data


def _discipline() -> str:
    """取材纪律：优先读知识库里的使用规则，回落到 content_library 索引的第 1 节。"""
    index_text = _read(skills_dir() / "xhs-daily" / "content_library" / "INDEX.md")
    match = re.search(r"(?ms)^##\s*1\..*?(?=^##\s*2\.)", index_text)
    return match.group(0).strip() if match else ""


def _pick_knowledge(task: dict) -> tuple[list[dict], dict]:
    """定位本篇知识条目：优先用 task.knowledge_ids，否则按 topic/problem 检索目录。"""
    query = " ".join(str(task.get(key) or "") for key in ("topic", "problem", "angle", "notes"))
    rows = kb.catalog()
    info = {"query": query.strip(), "mode": "", "candidates": []}
    if not rows:
        info["mode"] = "catalog_missing"
        return [], info
    wanted = [str(x).strip() for x in (task.get("knowledge_ids") or []) if str(x).strip()]
    if wanted:
        by_id = {row["id"]: row for row in rows}
        picked = [by_id[x] for x in wanted if x in by_id]
        info["mode"] = "task.knowledge_ids"
        info["missing_ids"] = [x for x in wanted if x not in by_id]
    else:
        picked, table = kb.locate(query, limit=int(task.get("knowledge_limit") or 3))
        info["mode"] = "catalog_locate"
        info["candidates"] = table
    out = []
    for row in picked:
        out.append({
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "path": row["path"],
            "refs": [x.strip() for x in re.split(r"[、,，]", row["source"]) if x.strip()],
            "text": row["text"][:CAP_KNOWLEDGE],
        })
    return out, info


def _material_ids(knowledge_items: list[dict], task: dict) -> list[str]:
    """素材编号来源：知识条目里的“依据” + 任务显式指定，保持出现顺序去重。"""
    ids = []
    for item in knowledge_items:
        for ref in item["refs"]:
            ref = ref.replace("素材", "").strip()
            if ref and ref not in ids:
                ids.append(ref)
    for extra in task.get("materials") or []:
        extra = str(extra).replace("素材", "").strip()
        if extra and extra not in ids:
            ids.append(extra)
    return ids


SYSTEM_PROMPT = """你是小红书图文账号的专职写稿人。账号面向娱乐主播（含颜值聊天、才艺互动），读者是想入行或刚开播、缺方法的人。

写作标准（必须遵守）：
1. 语气有信心，允许教学式、指导式、直接给判断；可以指出问题、解释原因、要求练习。
2. 效果表达相对肯定、具体：说清方法解决什么问题、给到什么能力，不用通篇"可能、也许、可以尝试"。
3. 每篇结构尽量是：具体问题 → 明确收益 → 原因分析 → 操作方法 → 示例或练习。
4. 不编造案例、公会扶持条件、收入或流量数字，不承诺"练几天必然有效"。真实方法可以给肯定判断，但不保证他人相同结果。
5. 卡片上的例句如果是示范话术，要标"示例"；不得把自己编的对话写成"我遇到过一个观众"这类真实案例。
6. 只输出一个 JSON 对象，不加解释、不加 Markdown 代码围栏。字段必须严格符合给定 schema。
7. 正文 200-400 字（按非空白字符计），短句、具体的直播间场景，不用书面套话；正文里不要写话题标签。
8. 六张卡片：第 1 张是封面（emoji + 主标题 + 副标题，**主标题最多 5 个汉字、副标题最多 10 个汉字**，渲染器字号固定，超了会断行）；后 5 张是正文卡，每张一个要点，用短行分句，**每张 11-13 行、每行不超过 12 字**（行数太少卡片下半页会空，实测 8 行只占一半版面）。
9. 材料里给了来源编号（如"素材 10"），那是给内部核对用的：**正文和卡片文案里一律不出现编号，也不出现「资料里」「原文里」「材料里」这类词**，读者不需要知道你的资料来源。要引用判断就直接说判断本身（如「顺序别搞反：先稳老粉，再点新人」）。
10. 材料没写的内容（尤其公会政策、分成比例、平台官方规则、具体收入）一律不写；材料不足以支撑时，在 risk_notes 里说明缺什么。
11. 出现的秒数、分钟数、比例、轮次只能来自材料；材料没给具体数字就不写数字，改成做法本身（如「上播前把三件事写下来」而不是「上播前 30 分钟做三件事」）。练习的轮次和时长可以写，但要明说是练习安排，不能写成「所有直播间都这样」。
12. 不写绝对化要求：不写「每个进场的人都必须被点名」「唯一」「一定」，除非材料明确如此。方法不等于规则，给建议给判断，但把「可以用这套顺序练」和「必须按这个顺序」分开。
13. 分清文章读者和直播里的观众：读者是想学方法的（多为主播或准备开播的人），直播里被互动的观众是普通观众，不一定播过。给「全场共同问题」这类示例时，问题必须是普通观众能回答的（聊生活、聊感受），不能问「你们开播第一句说什么」。
"""


def load_revise(task: dict) -> tuple[dict | None, list[str]]:
    """改稿模式：读回原稿，只把原稿 + 修改意见交给模型，要求只改相关部分。"""
    block = task.get("revise") or {}
    if not isinstance(block, dict):
        return None, ["task.revise 不是对象，已忽略"]
    source = str(block.get("from") or "").strip()
    if not source:
        return None, []
    path = Path(source)
    if path.is_dir():
        path = path / "draft.gpt.json"
    if not path.exists():
        return None, ["原稿不存在：%s" % path]
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        return None, ["原稿不是合法 JSON：%s（%s）" % (path, exc)]
    if not isinstance(data, dict):
        return None, ["原稿顶层不是对象：%s" % path]
    return {
        "data": data,
        "notes": str(block.get("notes") or "").strip(),
        "source": str(path),
    }, []


def build(task: dict, *, example_limit: int = 1, run_dir: Path | None = None,
          video: bool = False, budget: int = 26000) -> dict:
    fixed, fixed_missing = kb.fixed_context()
    picked, locate_info = _pick_knowledge(task)
    mat_ids = _material_ids(picked, task)
    revise, revise_notes = load_revise(task)

    # ---- 固定块（永不裁剪）----
    head = []
    head.append("## 一、本篇任务")
    head.append("系列：%s" % (task.get("series") or "未指定"))
    if task.get("seq"):
        head.append("序号：第 %s 篇" % task["seq"])
    head.append("主题：%s" % task["topic"])
    head.append("目标受众：%s" % task.get("audience"))
    head.append("要解决的问题：%s" % task["problem"])
    if task.get("angle"):
        head.append("切入角度：%s" % task["angle"])
    if task.get("notes"):
        head.append("额外要求：%s" % task["notes"])
    if locate_info["mode"] == "catalog_locate" and picked:
        head.append("本次定位到的知识条目：%s（按主题检索知识目录自动匹配）"
                    % "、".join("%s %s" % (x["id"], x["title"]) for x in picked))

    numerals = ["二", "三", "四", "五", "六", "七", "八"]
    for index, item in enumerate(fixed):
        head.append("\n## %s、%s" % (numerals[min(index, len(numerals) - 1)], item["title"]))
        head.append(item["text"])

    discipline = _discipline()
    if discipline:
        head.append("\n## 取材纪律")
        head.append(discipline)

    base = "\n".join(head)
    room = max(3000, budget - len(base))
    used, skipped = [], []

    # ---- 知识条目 ----
    blocks = []
    if picked:
        section = ["\n## 本篇相关知识（判断依据与适用条件，只能取方法与结构，用自己的话重组）"]
        for item in picked:
            chunk = "### %s %s（状态：%s）\n%s" % (item["id"], item["title"], item["status"], item["text"])
            if len(chunk) > room - 200:
                skipped.append({"type": "knowledge", "id": item["id"], "reason": "预算不足"})
                continue
            section.append(chunk)
            room -= len(chunk)
            used.append({"type": "knowledge", "id": item["id"], "title": item["title"],
                         "path": item["path"], "status": item["status"], "chars": len(chunk)})
        if len(section) > 1:
            blocks.append("\n".join(section))

    # ---- 本条知识的限制与误用（不能只给支持某种做法的片段）----
    if picked:
        limit_section = ["\n## 这些条目的适用边界与常见误用（写的时候必须一起考虑）"]
        for item in picked:
            detail = kb.sections(item["path"])
            rows = []
            for key in ("适用情况 / 判断要看什么", "常见误用", "状态"):
                if detail.get(key):
                    rows.append("- %s：%s" % (key.replace(" / 判断要看什么", ""), detail[key]))
            if rows:
                limit_section.append("### %s\n%s" % (item["id"], "\n".join(rows)))
        if len(limit_section) > 1:
            block = "\n".join(limit_section)
            blocks.append(block)
            room -= len(block)

    # ---- 素材摘要 ----
    mat_section = ["\n## 本篇资料来源摘要（原始资料，未经实际验证，只能当“资料观点”用）"]
    got_material = 0
    for mid in mat_ids:
        if room <= 600:
            skipped.append({"type": "material", "id": mid, "reason": "预算不足"})
            continue
        summary = kb.material_summary(mid)
        if not summary:
            skipped.append({"type": "material", "id": mid, "reason": "知识库无此素材"})
            continue
        text = summary["text"][:min(CAP_MATERIAL, room - 200)]
        chunk = "### 素材 %s｜%s\n%s" % (mid, summary["title"], text)
        mat_section.append(chunk)
        room -= len(chunk)
        got_material += 1
        used.append({"type": "material", "id": mid, "title": summary["title"],
                     "path": summary["path"], "chars": len(chunk)})
    if got_material:
        blocks.append("\n".join(mat_section))

    # ---- 原文片段（只在还有预算时补，最多 2 段）----
    excerpt_section = ["\n## 转写原文片段（口播原文，有口头语与转写错字，只取方法）"]
    got_excerpt = 0
    for mid in mat_ids:
        if got_excerpt >= 2 or room <= 800:
            break
        excerpt = kb.raw_excerpt(mid, locate_info["query"], max_chars=min(CAP_EXCERPT, room - 300))
        if not excerpt:
            continue
        chunk = "### 素材 %s 原文片段（%s）\n%s" % (mid, excerpt["file"], excerpt["text"])
        excerpt_section.append(chunk)
        room -= len(chunk)
        got_excerpt += 1
        used.append({"type": "excerpt", "id": mid, "file": excerpt["file"], "chars": len(chunk)})
    if got_excerpt:
        blocks.append("\n".join(excerpt_section))

    # ---- 范例（白名单）----
    examples, example_notes = kb.approved_examples(exclude=run_dir, limit=max(0, example_limit))

    parts = [base] + blocks

    if revise:
        parts.append("\n## 改稿模式（只改指定部分，不要整篇重写）")
        parts.append("原稿 JSON：\n" + json.dumps(revise["data"], ensure_ascii=False, indent=2))
        parts.append("修改意见：%s" % (revise["notes"] or "（主人没写具体意见，默认只做语言精炼，事实与结构不动）"))
        parts.append("要求：只改与修改意见直接相关的字段或段落，其余保持原样；输出仍是完整 JSON，但不是新写一篇。")

    if examples:
        parts.append("\n## 已认可范例（主人明确认可的作品，只参考语气、密度与结构，不要复用内容）")
        for item in examples:
            note = "（主人备注：%s）" % item["note"] if item["note"] else ""
            parts.append("标题：%s%s\n正文：%s" % (item["title"], note, item["body"][:CAP_EXAMPLE]))

    parts.append("\n## 输出要求")
    parts.append("只输出 JSON 对象，字段如下：")
    parts.append(
        "title：≤20 字的标题，具体钩子，不用夸张承诺；\n"
        "content：正文 200-400 字，分段用 \\n，不含话题标签；\n"
        "tags：5-8 个话题词，不带 # 号，不带空格；\n"
        "cover：{emoji, title(最多 5 个汉字), subtitle(最多 10 个汉字)}；\n"
        "cards：恰好 5 个对象，每个 {text}，text 用 \\n 分行，是该页全部文案；\n"
        "risk_notes：字符串数组，列出你不确定或需要人工确认的点（没有就空数组）。"
    )
    if video:
        parts.append("video：因为本机已启用视频能力，额外给 {outline: [页面要点 3-5 条], script: 60-120 秒讲稿}；")
    if task.get("tags_hint"):
        parts.append("建议话题方向（可调整，不要照抄超出的无关词）：%s" % "、".join(task["tags_hint"]))
    parts.append("\nJSON schema 见下（严格模式）：\n" + json.dumps(SCHEMA, ensure_ascii=False))

    user_prompt = "\n".join(parts)
    stats = {
        "system_chars": len(SYSTEM_PROMPT),
        "user_chars": len(user_prompt),
        "budget": budget,
        "knowledge": [x["id"] for x in picked],
        "knowledge_list": [{"id": x["id"], "title": x["title"], "status": x["status"]} for x in picked],
        "knowledge_status": [x["status"] for x in picked],
        "materials": [x["id"] for x in used if x["type"] == "material"],
        "excerpts": [x["id"] for x in used if x["type"] == "excerpt"],
        "examples": [x["dir"] for x in examples],
        "example_notes": example_notes,
        "fixed_missing": fixed_missing,
        "locate": locate_info,
        "skipped": skipped,
        "video": bool(video),
        "revise_from": revise["source"] if revise else "",
        "revise_notes": revise["notes"] if revise else "",
        "revise_problems": revise_notes,
    }
    record = {
        "built_at": "",
        "budget": budget,
        "total_chars": len(SYSTEM_PROMPT) + len(user_prompt),
        "fixed": [{"title": x["title"], "path": x["path"], "chars": len(x["text"])} for x in fixed],
        "locate": locate_info,
        "used": used,
        "examples": examples,
        "example_notes": example_notes,
        "skipped": skipped,
        "knowledge_texts": [{"id": x["id"], "status": x["status"], "chars": len(x["text"])} for x in picked],
    }
    return {"system": SYSTEM_PROMPT, "user": user_prompt, "stats": stats, "record": record}
