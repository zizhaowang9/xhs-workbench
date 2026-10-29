# -*- coding: utf-8 -*-
"""知识库读取层。

职责（对应 2026-10-29 的接入要求）：
1. 固定读：业务总纲（定位 / 已确认事实 / 当前有效规则）+ 表达标准 + 当前任务进度。
2. 先查知识目录定位条目，再按条目“依据”回原始素材摘要，必要时从转写原文取片段。
3. 只在知识库里找材料，不读别的目录；找不到就如实返回缺失。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import XHS_ROOT

BOARD_ORDER = ["A", "B", "C", "D", "E", "F"]

# 口语 → 知识词，用于“换个问法也能找到”
SYNONYMS = {
    "没人说话": ["沉默", "空窗", "独白", "冷场"],
    "不说话": ["沉默", "空窗", "独白"],
    "冷场": ["空窗", "沉默", "独白", "开场"],
    "安静": ["沉默", "空窗"],
    "尴尬": ["沉默", "空窗", "接话"],
    "插不进": ["新人", "老粉", "公平"],
    "插不上": ["新人", "老粉", "公平"],
    "新观众": ["新人", "公平"],
    "新人": ["新人", "公平", "进人"],
    "老粉": ["老粉", "分层", "公平"],
    "老观众": ["老粉", "分层"],
    "常来的": ["老粉", "分层"],
    "夸": ["夸奖", "弹幕"],
    "漂亮": ["夸奖", "人设"],
    "骂": ["抬杠", "边界", "负面"],
    "杠": ["抬杠", "边界"],
    "怼": ["抬杠", "边界"],
    "黑粉": ["抬杠", "边界", "负面"],
    "礼物": ["礼物", "转化", "分层"],
    "打赏": ["礼物", "转化"],
    "刷": ["礼物", "转化"],
    "累": ["倦怠", "内耗", "可控"],
    "没状态": ["倦怠", "镜头", "状态"],
    "不想播": ["倦怠", "内耗"],
    "焦虑": ["可控", "内耗"],
    "换号": ["换号", "限流"],
    "新号": ["换号"],
    "限流": ["换号", "限流"],
    "复盘": ["复盘", "数据", "录播"],
    "数据": ["复盘", "数据"],
    "灯": ["灯", "画面", "画面光"],
    "光线": ["灯", "画面"],
    "画面": ["灯", "播感"],
    "人设": ["人设", "标签"],
    "标签": ["人设"],
    "紧张": ["镜头", "状态", "开场"],
    "素颜": ["妆造", "准备"],
    "开播前": ["准备", "检查", "开场"],
    "第一句": ["开场", "欢迎", "进人"],
    "欢迎": ["进人", "欢迎"],
    "进人": ["进人", "欢迎"],
    "话题": ["话题", "空窗", "展开"],
    "情绪": ["情绪", "情绪价值", "感知"],
    "抑郁": ["倦怠", "内耗"],
    "团播": ["团播", "个播"],
    "个播": ["个播", "团播"],
    "切片": ["切片", "引流"],
    "视频": ["切片", "引流"],
    "招募": ["招募", "阶段"],
    "分成": ["招募"],  # 知识库没有政策，仅用于让“无答案”显式暴露
    "公会": ["招募"],
}


def knowledge_dir() -> Path:
    paths_file = XHS_ROOT / "config" / "paths.json"
    if paths_file.exists():
        try:
            data = json.loads(paths_file.read_text(encoding="utf-8-sig"))
            value = data.get("knowledge_dir")
            if value:
                return Path(value)
        except ValueError:
            pass
    return XHS_ROOT / "knowledge"


def _read(path: Path) -> str:
    try:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _section(text: str, heading: str) -> str:
    """取 `## heading` 到下一个 `## ` 之间的内容。"""
    match = re.search(r"(?ms)^##\s*%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(heading), text)
    return match.group(1).strip() if match else ""


def _strip_front(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].lstrip("\n")
    return text


def sections(path) -> dict:
    """取条目里的关键小节（适用情况 / 具体怎么做 / 常见误用 / 状态），

    目的是让写稿模型同时拿到“限制与误用”，而不是只取支持某种做法的片段。
    """
    if not path:
        return {}
    text = _read(Path(path))
    if not text:
        return {}
    body = _strip_front(text)
    out = {}
    for key in ("适用情况 / 判断要看什么", "具体怎么做", "常见误用", "状态"):
        value = _section(body, key)
        if value:
            out[key] = value
    return out


def _front(text: str) -> dict:
    meta = {}
    if not text.startswith("---"):
        return meta
    parts = text.split("---", 2)
    if len(parts) < 3:
        return meta
    for line in parts[1].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


# ---------------- 固定上下文 ----------------

FIXED_FILES = [
    ("账号定位", "01-业务总纲/01-账号定位.md"),
    ("已确认业务事实", "01-业务总纲/03-已确认业务事实.md"),
    ("当前有效规则", "01-业务总纲/04-当前有效规则.md"),
    ("表达标准与主人反馈", "01-业务总纲/02-表达标准与反馈.md"),
]


def fixed_context() -> tuple[list[dict], list[str]]:
    """每次都必须读的总纲与规则，返回 [(title, text)] 与缺失列表。"""
    base = knowledge_dir()
    out, missing = [], []
    for title, rel in FIXED_FILES:
        text = _read(base / rel.replace("/", "\\"))
        if not text:
            missing.append(rel)
            continue
        out.append({"title": title, "path": rel, "text": _strip_front(text).strip()})
    progress = _read(base / "06-工作记录" / "01-当前任务.md")
    if progress:
        out.append({"title": "当前任务进度", "path": "06-工作记录/01-当前任务.md",
                    "text": _strip_front(progress).strip()})
    else:
        missing.append("06-工作记录/01-当前任务.md")
    return out, missing


# ---------------- 知识目录索引 ----------------

def catalog() -> list[dict]:
    """扫 03-运营知识 的 frontmatter，得到条目索引（等价于知识目录）。"""
    base = knowledge_dir() / "03-运营知识"
    if not base.exists():
        return []
    rows = []
    for path in sorted(base.rglob("*.md")):
        if path.name.startswith("00-"):
            continue
        text = _read(path)
        meta = _front(text)
        if meta.get("type") != "运营知识":
            continue
        body = _strip_front(text)
        title_match = re.search(r"(?m)^#\s+(.+)$", body)
        rows.append({
            "id": meta.get("id", ""),
            "board": meta.get("板块", ""),
            "status": meta.get("状态", ""),
            "source": meta.get("依据", ""),
            "keywords": meta.get("关键词", ""),
            "title": (title_match.group(1).strip() if title_match else path.stem),
            "path": str(path.relative_to(knowledge_dir())),
            "head": " ".join([_section(body, "解决什么问题"), _section(body, "适用情况 / 判断要看什么")]),
            "text": body,
        })
    rows.sort(key=lambda r: (r["id"][:1], r["id"]))
    return rows


def _grams(text: str) -> set[str]:
    clean = re.sub(r"[\s，。、？！：；“”‘’（）()\[\]【】,.!?:;\"'-]+", "", text)
    return {clean[i:i + 2] for i in range(len(clean) - 1)} if len(clean) > 1 else ({clean} if clean else set())


def _expand(query: str) -> list[str]:
    extra = []
    for key, words in SYNONYMS.items():
        if key in query:
            extra.extend(words)
    return extra


def locate(query: str, limit: int = 3) -> tuple[list[dict], list[dict]]:
    """按查询定位知识条目。

    打分三路并用：①关键词表命中（强信号，权重最高）②标题/判断段的二字组重合
    ③口语同义词扩展命中。关键词表就是给“换个问法”用的。
    """
    rows = catalog()
    if not rows:
        return [], []
    text = str(query or "")
    q = _grams(text)
    extra = _expand(text)
    scored = []
    for row in rows:
        words = [w.strip() for w in str(row.get("keywords") or "").split(",") if w.strip()]
        kw_hit = [w for w in words if w and w in text]
        extra_hit = [w for w in extra if w and (w in str(row.get("keywords") or "") or w in row["title"] or w in row["head"])]
        target = " ".join([row["title"], row["board"], row["head"]])
        t = _grams(target)
        gram = len(q & t) / max(1, len(q)) if q else 0.0
        score = min(1.2, 0.55 * len(kw_hit)) + 0.9 * gram + min(0.4, 0.12 * len(extra_hit))
        scored.append((score, row, kw_hit))
    scored.sort(key=lambda x: -x[0])
    picked = [row for score, row, _ in scored if score >= 0.6][:limit]
    if not picked:
        picked = [row for score, row, _ in scored[:1] if score > 0.35]
    table = [{"id": r["id"], "title": r["title"], "score": round(sc, 3), "kw": hits}
             for sc, r, hits in scored[:6]]
    return picked, table


# ---------------- 原始素材 ----------------

def _material_file(mid: str) -> Path | None:
    base = knowledge_dir() / "02-原始资料"
    if not base.exists():
        return None
    keys = set()
    for part in str(mid).split("/"):
        part = part.strip()
        if part.isdigit():
            keys.add(int(part))
    if not keys:
        return None
    for path in sorted(base.glob("*.md")):
        m = re.match(r"素材\s*(\d+)", path.name)
        if m and int(m.group(1)) in keys:
            return path
    return None


def material_summary(mid: str) -> dict | None:
    path = _material_file(mid)
    if not path:
        return None
    text = _read(path)
    meta = _front(text)
    body = _strip_front(text)
    summary = _section(body, "内容摘要")
    if not summary:
        return None
    title_match = re.search(r"(?m)^#\s+(.+)$", body)
    return {
        "id": mid,
        "title": title_match.group(1).strip() if title_match else path.stem,
        "path": str(path.relative_to(knowledge_dir())),
        "text": summary,
    }


def raw_excerpt(mid: str, query: str = "", max_chars: int = 2200) -> dict | None:
    """从转写原文取相关片段（按关键词命中选窗口，不从头硬切）。"""
    base = knowledge_dir() / "02-原始资料" / "原文"
    if not base.exists():
        return None
    keys = [p for p in mid.split("/") if p]
    files = []
    for path in sorted(base.glob("*.txt")):
        head = path.name.split("-")[0]
        if head in keys:
            files.append(path)
    if not files:
        return None
    q = _grams(query) if query else set()
    best = None
    for path in files:
        text = _read(path)
        if not text:
            continue
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            continue
        if q:
            window = 14
            best_local = (0, 0)
            for start in range(0, max(1, len(lines) - 4)):
                chunk = "\n".join(lines[start:start + window])
                score = len(q & _grams(chunk))
                if score > best_local[0]:
                    best_local = (score, start)
            start = best_local[1]
            snippet = "\n".join(lines[max(0, start - 2):start + 12])
        else:
            snippet = "\n".join(lines[:24])
        if best is None or len(snippet) > len(best["text"]):
            best = {"id": mid, "file": path.name, "text": snippet[:max_chars]}
    return best


# ---------------- 范例白名单 ----------------

APPROVED_FILE = XHS_ROOT / "config" / "style_examples.json"


def approved_examples(exclude: Path | None = None, limit: int = 1) -> tuple[list[dict], list[str]]:
    """只返回主人明确认可的作品。没有白名单文件或为空 → 不提供范例。"""
    notes = []
    if not APPROVED_FILE.exists():
        return [], ["无认可范例白名单（%s 不存在），本次不提供写作范例" % APPROVED_FILE.name]
    try:
        data = json.loads(APPROVED_FILE.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        return [], ["白名单不是合法 JSON：%s" % exc]
    items = data.get("approved") or []
    if not items:
        return [], ["白名单为空，本次不提供写作范例"]
    out = []
    for item in items:
        rel = str(item.get("run_dir") or "").strip()
        if not rel:
            continue
        run = Path(rel)
        if not run.is_absolute():
            run = XHS_ROOT / rel
        if exclude and run.resolve() == Path(exclude).resolve():
            notes.append("跳过本篇自身：%s" % run.name)
            continue
        content = _read(run / "content.txt").strip()
        meta_text = _read(run / "gpt_meta.json")
        if not content:
            notes.append("白名单目录缺 content.txt：%s" % run.name)
            continue
        try:
            meta = json.loads(meta_text) if meta_text else {}
        except ValueError:
            meta = {}
        if meta.get("mode") == "mock" or meta.get("real_call") is False:
            notes.append("白名单里的 mock/测试稿已跳过：%s" % run.name)
            continue
        body = "\n".join(line for line in content.splitlines() if not line.strip().startswith("#"))
        out.append({
            "dir": run.name,
            "title": _read(run / "title.txt").strip(),
            "body": body.strip()[:700],
            "note": str(item.get("note") or "").strip(),
        })
        if len(out) >= max(1, limit):
            break
    if not out:
        notes.append("白名单中没有可用作品，本次不提供写作范例")
    return out, notes
