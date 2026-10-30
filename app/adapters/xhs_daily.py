# -*- coding: utf-8 -*-
"""日常出稿适配脚本（本地补丁）。

    python xhs_daily.py bridge-status
    python xhs_daily.py fill-new --workdir <工作目录> [--leave]
    python xhs_daily.py verify-draft --workdir <工作目录>

设计约束：
- 只填写表单 / 保存草稿，永不点击「发布」；
- 遇到底色改版时用「文本 + 视口内可见」定位，不依赖易变 class 名；
- 正文与话题都用 contenteditable 局部插入（execCommand insertText / 逐字 input），
  不清空整框，避免丢掉已插入的图片和已写好的正文；
- 只有真实读回并比对过，才允许说「已写入 / 已核验」。
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

from common import load_paths, load_bridge_module, make_page

PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish?source=official"
MAX_TITLE = 20
STEPS = ("prepared", "filled", "drafted", "verified", "unconfirmed", "failed")

# ---------------------------------------------------------------- JS 片段

JS_FIND_VISIBLE_TEXT = """
(() => {
  const T = %s;
  const nodes = [...document.querySelectorAll('div,span,a,button,li,label,p')];
  const leaves = nodes.filter(e => e.textContent.trim() === T &&
      ![...e.children].some(c => c.textContent.trim() === T));
  const cand = leaves.map(e => ({e, r: e.getBoundingClientRect()}))
    .filter(o => o.r.width > 4 && o.r.height > 4 && o.r.left >= 0 && o.r.top >= 0 &&
                 o.r.right <= innerWidth + 2 && o.r.bottom <= innerHeight + 2)
    .sort((a, b) => a.r.width * a.r.height - b.r.width * b.r.height);
  if (!cand.length) return {ok: false, total: leaves.length, vw: innerWidth, vh: innerHeight};
  const r = cand[0].r;
  return {ok: true, x: r.left + r.width / 2, y: r.top + r.height / 2};
})()
"""

JS_EDITOR_FOCUS_END = """
(() => {
  const ed = document.querySelector('div.tiptap.ProseMirror') ||
             document.querySelector('[contenteditable="true"]');
  if (!ed) return {ok: false, reason: 'editor-not-found'};
  ed.focus();
  const sel = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(ed);
  range.collapse(false);
  sel.removeAllRanges();
  sel.addRange(range);
  return {ok: true, len: (ed.innerText || '').length, focused: document.activeElement === ed};
})()
"""

JS_INSERT_TEXT = """
(() => {
  const ed = document.querySelector('div.tiptap.ProseMirror') ||
             document.querySelector('[contenteditable="true"]');
  if (!ed) return {ok: false, reason: 'editor-not-found'};
  ed.focus();
  const sel = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(ed);
  range.collapse(false);
  sel.removeAllRanges();
  sel.addRange(range);
  const ok = document.execCommand('insertText', false, %s);
  return {ok: ok, len: (ed.innerText || '').length};
})()
"""

JS_SUGGESTION = """
(() => {
  const s = document.querySelector('.tiptap .suggestion, .ProseMirror .suggestion, span.suggestion');
  return {text: s ? s.textContent.trim() : null};
})()
"""

JS_READ_EDITOR = """
(() => {
  const ed = document.querySelector('div.tiptap.ProseMirror') ||
             document.querySelector('[contenteditable="true"]');
  if (!ed) return {ok: false, reason: 'editor-not-found'};
  const text = ed.innerText || '';
  const tags = text.match(/#[\\u4e00-\\u9fa5A-Za-z0-9_]+/g) || [];
  // 真话题节点：编辑器把选中的话题渲染成 a / span.mention / data-topic
  const nodes = [...ed.querySelectorAll('a, span.mention, span[data-topic], [data-topic]')];
  const topicNodes = nodes
    .map(n => (n.getAttribute('data-topic') || n.textContent || '').trim())
    .filter(t => t && t.charAt(0) === '#');
  const slides = document.querySelectorAll('.swiper-slide');
  const imgs = [...slides].map(s => {
    const i = s.querySelector('img');
    return i ? {w: i.naturalWidth, h: i.naturalHeight, src: (i.currentSrc || i.src || '').slice(0, 24)} : null;
  });
  const input = document.querySelector('input[placeholder*="标题"]');
  return {
    ok: true,
    title: input ? input.value : null,
    text: text,
    chars: text.replace(/\\s/g, '').length,
    tags: tags,
    tag_count: tags.length,
    topic_nodes: topicNodes,
    topic_node_count: topicNodes.length,
    slides: slides.length,
    imgs: imgs
  };
})()
"""

JS_DRAFT_LIST = """
(() => {
  const items = [...document.querySelectorAll('.draft-item')];
  const rows = items.map(it => ({
    title: (it.querySelector('.draft-title-text') || {}).textContent || '',
    time: (it.querySelector('.draft-time') || {}).textContent || '',
    hasBtn: !!it.querySelector('.btn')
  }));
  const tabs = [...document.querySelectorAll('.tab-item')].map(t => ({
    text: t.textContent.trim(),
    active: t.className.includes('active')
  }));
  return {count: items.length, rows: rows, tabs: tabs};
})()
"""

JS_CLICK_TAB = """
(() => {
  const tabs = [...document.querySelectorAll('.tab-item')];
  const t = tabs.find(x => x.textContent.includes('图文'));
  if (!t) return {ok: false, tabs: tabs.map(x => x.textContent.trim())};
  t.click();
  return {ok: true};
})()
"""

JS_CLICK_DRAFT_BY_TITLE = """
(() => {
  const T = %s;
  const norm = s => (s || '').replace(/\\s+/g, '');
  const items = [...document.querySelectorAll('.draft-item')];
  const matches = items.map((it, index) => ({it, index})).filter(({it}) => norm((it.querySelector('.draft-title-text') || {}).textContent) === norm(T));
  if (matches.length !== 1) return {ok: false, reason: matches.length > 1 ? 'ambiguous' : 'not-found', count: matches.length,
    titles: items.map(it => ((it.querySelector('.draft-title-text') || {}).textContent || '').trim()),
    candidates: matches.map(({it, index}) => ({index, title: ((it.querySelector('.draft-title-text') || {}).textContent || '').trim(), time: ((it.querySelector('.draft-time') || {}).textContent || '').trim()}))};
  const {it, index: idx} = matches[0];
  const btn = it.querySelector('.btn') || it;
  btn.click();
  return {ok: true, index: idx};
})()
"""


# ---------------------------------------------------------------- 工具函数


def _click_visible_text(page, text: str, desc: str, tries: int = 20) -> None:
    """按「文本完全匹配 + 在视口内」定位，再用真实鼠标点击。"""
    expr = JS_FIND_VISIBLE_TEXT % json.dumps(text)
    for _ in range(tries):
        res = page.evaluate(expr)
        if isinstance(res, dict) and res.get("ok"):
            page.mouse_move(res["x"], res["y"])
            time.sleep(0.12)
            page.mouse_click(res["x"], res["y"], "left")
            return
        time.sleep(0.5)
    raise SystemExit(f"没找到可点击的「{desc}」，可能是页面结构改版，请人工检查。")


def _wait(predicate, timeout: float, interval: float = 0.5):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def _load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def _split_content(raw: str):
    """把正文拆成（正文主体, 话题列表），话题以 # 开头的行尾为准。"""
    lines = [ln.rstrip() for ln in raw.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    body_lines, tags = lines, []
    if body_lines:
        last = body_lines[-1].strip()
        found = re.findall(r"#[^\s#]+", last)
        if found and last.startswith("#"):
            tags = [t.lstrip("#") for t in found]
            body_lines = body_lines[:-1]
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    return "\n".join(body_lines).strip(), tags


def _png_size(path: Path):
    """读 PNG 头拿宽高，避免依赖 Pillow。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(33)
        if head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    except OSError:
        return None


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- 每篇状态


def state_path(workdir: Path) -> Path:
    return workdir / "state.json"


def load_state(workdir: Path) -> dict:
    p = state_path(workdir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(workdir: Path, state: dict) -> None:
    state["updated_at"] = _now()
    state["stage"] = state.get("stage") or "prepared"
    p = state_path(workdir)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _workdir_from(args) -> Path:
    """工作目录：优先 --workdir；否则由 title-file / content-file 反推。"""
    if getattr(args, "workdir", None):
        return Path(args.workdir).expanduser().resolve()
    for attr in ("title_file", "content_file"):
        p = getattr(args, attr, None)
        if p:
            return Path(p).expanduser().resolve().parent
    raise SystemExit("请用 --workdir 指定本次稿件的工作目录。")


def _read_workdir(workdir: Path):
    title_file = workdir / "title.txt"
    content_file = workdir / "content.txt"
    images_dir = workdir / "images"
    if not title_file.exists():
        raise SystemExit(f"工作目录里缺少 title.txt：{title_file}")
    if not content_file.exists():
        raise SystemExit(f"工作目录里缺少 content.txt：{content_file}")
    title = _load_text(str(title_file))
    raw_body, tags = _split_content(_load_text(str(content_file)))
    names = ["cover.png"] + [f"card_{i}.png" for i in range(1, 6)]
    images = [images_dir / n for n in names]
    return title, raw_body, tags, images


# ---------------------------------------------------------------- 命令


def cmd_bridge_status(_args) -> int:
    paths = load_paths()
    BridgePage, check_login_status = load_bridge_module(paths)
    page = BridgePage(paths.get("bridge_url", "ws://localhost:9333"))

    server = page.is_server_running()
    print(f"[1/3] Bridge 服务运行中: {'是' if server else '否'}")
    if not server:
        print("      处理：双击安装目录里的「启动助手.cmd」，运行期间保留窗口。")
        return 1

    ext = page.is_extension_connected()
    print(f"[2/3] 浏览器扩展已连接: {'是' if ext else '否'}")
    if not ext:
        print("      处理：在 Chrome 打开扩展管理页，启用并加载安装目录里的 XHS Bridge 扩展，")
        print("            然后刷新一次小红书页面。")
        return 2

    logged = check_login_status(page)
    print(f"[3/3] 小红书已登录: {'是' if logged else '否'}")
    if not logged:
        print("      处理：在 Chrome 中打开小红书并手动登录（本工具不会代登录、不导出 Cookie）。")
        return 3

    print("结论：桥接、扩展、登录均就绪，可以开始出稿。")
    return 0


def cmd_env_probe(_args) -> int:
    """给「检查环境.cmd」用的机器可读探测：Bridge / 扩展 / 登录 三态分开。"""
    result = {"bridge": False, "extension": False, "login": None, "error": ""}
    try:
        paths = load_paths()
        BridgePage, check_login_status = load_bridge_module(paths)
        page = BridgePage(paths.get("bridge_url", "ws://localhost:9333"))
        result["bridge"] = bool(page.is_server_running())
        if result["bridge"]:
            result["extension"] = bool(page.is_extension_connected())
            if result["extension"]:
                try:
                    result["login"] = bool(check_login_status(page))
                except Exception as exc:  # 登录态读取失败不等于依赖问题
                    result["login"] = None
                    result["error"] = f"登录状态检查异常: {exc}"
    except Exception as exc:
        result["error"] = str(exc)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _insert_topics(page, tags):
    """往正文末尾逐个写话题，不清空正文。

    返回 (真话题, 纯文本话题)：联想词恰好等于目标 #词时才按回车选中；
    否则保留纯文本 #词（已输入的文字不会丢）。
    """
    picked, plain = [], []
    for tag in tags:
        page.evaluate(JS_EDITOR_FOCUS_END)
        # 逐字输入：扩展在 contenteditable 里用 document.execCommand('insertText', char)
        # 只在光标处插入，不会 selectAll / 清空已有正文
        page.type_text(f"#{tag}", 40)
        time.sleep(0.4)
        sug = page.evaluate(JS_SUGGESTION)
        ghost = (sug or {}).get("text") if isinstance(sug, dict) else None
        if ghost == f"#{tag}":
            page.press_key("Enter")
            time.sleep(0.25)
            picked.append(tag)
        else:
            # 没有精确匹配的联想词：保留纯文本话题，用空格隔开下一个
            page.evaluate(JS_INSERT_TEXT % json.dumps(" ", ensure_ascii=False))
            plain.append(tag)
            time.sleep(0.1)
    return picked, plain


def compare_filled(title, raw_body, tags, detail):
    """填页后立即读回核对：返回 (不匹配项, 读回信息)。"""
    detail = detail if isinstance(detail, dict) else {}
    read_tags = [t.lstrip("#") for t in (detail.get("tags") or [])]
    missed = [t for t in tags if t not in read_tags]
    problems = []
    if _norm(detail.get("title")) != _norm(title):
        problems.append(f"标题读回不一致（读到：{detail.get('title')!r}）")
    body = _norm(raw_body)
    if not body or body not in _norm(detail.get("text")):
        problems.append("正文读回对不上（可能只写入了部分内容）")
    if missed:
        problems.append("以下话题没有出现在正文里：" + " ".join("#" + t for t in missed))
    slides = detail.get("slides", 0)
    if slides != 6:
        problems.append(f"图片数量异常：{slides}（应为 6）")
    return problems, {"read_tags": read_tags, "missed": missed, "slides": slides}


def compare_draft(title, raw_body, tags, images, detail):
    """重新打开草稿后的核验：返回 (不匹配项, 读回信息)。空列表表示通过。"""
    detail = detail if isinstance(detail, dict) else {}
    problems = []

    # 1) 标题
    got_title = (detail.get("title") or "").strip()
    if _norm(got_title) != _norm(title):
        problems.append(f"标题不一致：本地「{title}」/ 草稿「{got_title}」")

    # 2) 正文：去除末行话题后精确比较（忽略平台空白差异）
    remote_text = _norm(detail.get("text"))
    local_text = _norm(raw_body)
    if not local_text:
        problems.append("本地正文是空的，无法比对")
    elif local_text != _norm(_split_content(detail.get("text") or "")[0]):
        problems.append(f"正文对不上：本地 {len(local_text)} 字，草稿 {len(remote_text)} 字（去空白）")

    # 3) 全部话题
    remote_tags = [t.lstrip("#") for t in (detail.get("tags") or [])]
    missing_tags = [t for t in tags if t not in remote_tags]
    extra_tags = [t for t in remote_tags if t not in tags]
    if missing_tags:
        problems.append("草稿里缺少话题：" + " ".join("#" + t for t in missing_tags))
    if extra_tags:
        problems.append("草稿里多出话题：" + " ".join("#" + t for t in extra_tags))

    if remote_tags != tags:
        problems.append("话题名称、数量或顺序不一致")
    topic_nodes = [str(t).lstrip("#") for t in (detail.get("topic_nodes") or [])]
    if topic_nodes != tags:
        problems.append("话题节点未完整转换，或节点名称/顺序不一致")

    # 4) 六图数量与尺寸。相同宽高比不能确认内容或顺序，需另行目检。
    slides = detail.get("slides", 0)
    if slides != 6:
        problems.append(f"图片数量异常：{slides}（应为 6）")
    imgs = detail.get("imgs") or []
    ratios = []
    if len(images) != 6 or len(imgs) != 6:
        problems.append("本地或草稿图片详情不完整，应均为 6 张")
    for local, remote in zip(images, imgs):
        size = _png_size(local)
        if not size or not remote:
            ratios.append(None)
            continue
        lw, lh = size
        rw, rh = (remote.get("w") or 0), (remote.get("h") or 0)
        if not rw or not rh:
            ratios.append(None)
            continue
        ratios.append(((lw / lh), (rw / rh)))
    for i, pair in enumerate(ratios, start=1):
        if pair is None:
            problems.append(f"第 {i} 张图读不到尺寸，无法确认顺序")
            continue
        if abs(pair[0] - pair[1]) > 0.02:
            problems.append(f"第 {i} 张图宽高比不一致（本地 {pair[0]:.3f} / 草稿 {pair[1]:.3f}），顺序可能变了")

    return problems, {
        "title": got_title,
        "tags": remote_tags,
        "slides": slides,
        "ratios": ratios,
        "chars": len(remote_text),
    }


def should_resume_existing(state: dict, title: str) -> bool:
    """An identified draft or failed attempt must be continued, never recreated."""
    if state.get("stage") == "failed" or (state.get("draft") or {}).get("identity"):
        return True
    return (state.get("stage") in ("filled", "drafted", "verified", "unconfirmed", "failed")
            and _norm(state.get("title")) == _norm(title))


def cmd_fill_new(args) -> int:
    paths = load_paths()
    workdir = _workdir_from(args)

    title = _load_text(args.title_file) if args.title_file else _load_text(str(workdir / "title.txt"))
    if len(title) > MAX_TITLE:
        raise SystemExit(f"标题 {len(title)} 字，超过 {MAX_TITLE} 字上限，请先精简。")
    raw_body, tags = _split_content(
        _load_text(args.content_file) if args.content_file else _load_text(str(workdir / "content.txt"))
    )

    image_dir = Path(args.images_dir) if args.images_dir else workdir / "images"
    names = ["cover.png"] + [f"card_{i}.png" for i in range(1, 6)]
    images = [image_dir / n for n in names]
    missing = [str(p) for p in images if not p.exists()]
    if missing:
        raise SystemExit("缺少图片：\n  " + "\n  ".join(missing))

    state = load_state(workdir)
    resume_existing = should_resume_existing(state, title)
    state.update(
        version=1,
        workdir=str(workdir),
        title=title,
        tags=tags,
        image_count=len(images),
    )

    if getattr(args, "dry_run", False):
        print("【演练模式】只检查输入，不打开浏览器、不写草稿")
        print(f"标题：{title}（{len(title)} 字）")
        print(f"正文：{len(raw_body)} 字")
        print(f"话题：{len(tags)} 个 -> {' '.join('#' + t for t in tags)}")
        print("图片：")
        for p in images:
            print(f"  {p.name}  {p.stat().st_size} bytes")
        # A dry run must not mutate an existing or new draft lifecycle state.
        return 0

    # 已有草稿就不重建：交给 verify-draft 继续这一篇
    if resume_existing:
        print(f"这一篇已经在进行中（阶段：{state.get('stage')}，标题：{title}）")
        print("按「已存在草稿走原稿继续」的规则，本次不重新建稿、不重复上传。")
        print("下一步：运行 verify-draft 核实这篇草稿是否真的保存成功。")
        return 0

    page = make_page(paths)
    if not page.is_server_running() or not page.is_extension_connected():
        raise SystemExit("Bridge 未运行或扩展未连接，请先双击安装目录里的「启动助手.cmd」并检查环境。")

    state.update(stage="unconfirmed", attempt_started_at=_now())
    save_state(workdir, state)

    print(f"→ 打开发布页（标题 {len(title)} 字，正文 {len(raw_body)} 字，话题 {len(tags)} 个）")
    page.navigate(PUBLISH_URL)
    time.sleep(2.5)

    _click_visible_text(page, "上传图文", "上传图文 标签页")
    time.sleep(1.5)

    selector = 'input[type=file][accept*="png"][multiple]'
    page.set_file_input(selector, [str(p.resolve()) for p in images])
    print("→ 已提交 6 张图片，等待上传完成…")

    def uploaded():
        res = page.evaluate(JS_READ_EDITOR)
        if not isinstance(res, dict) or not res.get("imgs"):
            return None
        done = [i for i in res["imgs"] if i and i.get("w", 0) > 0]
        return True if len(done) >= 6 else None

    if not _wait(uploaded, timeout=90):
        state.update(stage="failed", failed_at=_now(), failure="图片上传超时")
        save_state(workdir, state)
        raise SystemExit("图片上传超时，请到页面确认上传状态后重试。")
    print("→ 6 张图片已就绪")

    page.input_text('input[placeholder*="标题"]', title)
    time.sleep(0.4)

    focus = page.evaluate(JS_EDITOR_FOCUS_END)
    if not (isinstance(focus, dict) and focus.get("ok")):
        state.update(stage="failed", failed_at=_now(), failure="找不到正文编辑器")
        save_state(workdir, state)
        raise SystemExit("没找到正文编辑器，可能是页面改版，请人工检查。")
    page.evaluate(JS_INSERT_TEXT % json.dumps(raw_body, ensure_ascii=False))
    time.sleep(0.6)

    picked, plain = [], []
    if tags:
        page.evaluate(JS_EDITOR_FOCUS_END)
        page.evaluate(JS_INSERT_TEXT % json.dumps("\n", ensure_ascii=False))
        picked, plain = _insert_topics(page, tags)
        print(f"→ 话题输入完成：选中联想 {len(picked)} 个，纯文本 {len(plain)} 个")

    page.evaluate(JS_EDITOR_FOCUS_END)
    detail = page.evaluate(JS_READ_EDITOR)
    print(json.dumps(detail, ensure_ascii=False, indent=2))

    # 读回核对：话题、标题、正文、图片数都要真实对上
    problems, info = compare_filled(title, raw_body, tags, detail)
    read_tags = info["read_tags"]
    slides = info["slides"]

    state.update(
        stage="filled",
        filled_at=_now(),
        topics_picked=picked,
        topics_plain=plain,
        readback={
            "title": (detail or {}).get("title"),
            "chars": (detail or {}).get("chars"),
            "tags": read_tags,
            "topic_nodes": (detail or {}).get("topic_nodes"),
            "slides": slides,
        },
        draft={"identity": f"title:{title}", "opened_at": _now()},
    )
    save_state(workdir, state)

    if problems:
        print("内容没有全部写入，先别当成功：")
        for p in problems:
            print(f"  !! {p}")
        state.update(stage="filled", problems=problems)
        save_state(workdir, state)
        return 5

    print(f"→ 已读回确认：标题一致、正文完整、话题 {len(read_tags)} 个、图片 6 张")

    if args.leave:
        _click_visible_text(page, "笔记管理", "左侧「笔记管理」")
        time.sleep(2.0)
        state.update(stage="drafted", drafted_at=_now())
        save_state(workdir, state)
        print("→ 已离开编辑页，触发平台的静默暂存。")
        print("注意：这只代表「已提交暂存」，草稿是否真的保存下来还没确认。")
        print(f"下一步：运行 verify-draft --workdir \"{workdir}\" 重新打开核对。")
        return 0

    print("内容已填入页面，尚未核验保存（也没有点发布）。")
    print(f"下一步：加 --leave 离开编辑页触发暂存，或运行 verify-draft --workdir \"{workdir}\" 核对。")
    return 0


def cmd_verify_draft(args) -> int:
    paths = load_paths()
    workdir = _workdir_from(args)
    title, raw_body, tags, images = _read_workdir(workdir)
    state = load_state(workdir)
    state.update(version=1, workdir=str(workdir), title=title, tags=tags)

    page = make_page(paths)
    if not page.is_server_running() or not page.is_extension_connected():
        print("Bridge 未运行或扩展未连接，无法核验；本次不记录为通过。")
        return 5

    page.navigate(PUBLISH_URL)
    time.sleep(2.5)

    _click_visible_text(page, "草稿箱", "草稿箱入口")
    time.sleep(1.5)

    tab = page.evaluate(JS_CLICK_TAB)
    if not (isinstance(tab, dict) and tab.get("ok")):
        raise SystemExit(f"没找到「图文笔记」标签页：{tab}")
    time.sleep(1.2)

    listing = page.evaluate(JS_DRAFT_LIST)
    print("草稿箱：")
    print(json.dumps(listing, ensure_ascii=False, indent=2))

    if not listing.get("count"):
        state.update(stage="unconfirmed", verify={"ok": None, "checked_at": _now(), "problems": ["草稿箱里没有图文草稿"]})
        save_state(workdir, state)
        print("核验结果：未确认 —— 草稿箱里没有图文草稿，先核实再决定是否重新填。")
        return 5

    # 按本次标题定位这一篇，而不是永远打开第一篇
    clicked = page.evaluate(JS_CLICK_DRAFT_BY_TITLE % json.dumps(title, ensure_ascii=False))
    if not (isinstance(clicked, dict) and clicked.get("ok")):
        titles = (clicked or {}).get("titles") or []
        ambiguous = (clicked or {}).get("reason") == "ambiguous"
        reason = (f"标题「{title}」对应多条草稿；未点击，请按保存时间核对原稿" if ambiguous
                  else f"草稿箱里没有标题为「{title}」的草稿")
        state.update(
            stage="unconfirmed",
            verify={
                "ok": None,
                "checked_at": _now(),
                "problems": [reason],
                "draft_candidates": (clicked or {}).get("candidates") or [],
                "draft_titles": titles,
            },
        )
        save_state(workdir, state)
        print("核验结果：未确认 —— " + reason)
        if ambiguous:
            print(json.dumps((clicked or {}).get("candidates"), ensure_ascii=False))
        shown = "、".join([t for t in titles if t]) or "（空）"
        print("现有草稿标题：" + shown)
        print("先核实是否真的保存过，不要直接重复上传。")
        return 5
    print(f"→ 已打开匹配的草稿（第 {clicked.get('index', 0) + 1} 篇）")
    time.sleep(3.0)

    detail = page.evaluate(JS_READ_EDITOR)
    print("打开后的内容：")
    print(json.dumps(detail, ensure_ascii=False, indent=2))

    problems = []
    if not (isinstance(detail, dict) and detail.get("ok")):
        state.update(stage="unconfirmed", verify={"ok": None, "checked_at": _now(), "problems": ["没能读到编辑器内容"]})
        save_state(workdir, state)
        print("核验结果：未确认 —— 没能读到编辑器内容，不作通过。")
        return 5

    problems, info = compare_draft(title, raw_body, tags, images, detail)
    got_title = info["title"]
    remote_tags = info["tags"]
    slides = info["slides"]
    ratios = info["ratios"]
    for i, pair in enumerate(ratios, start=1):
        if pair is None:
            problems.append(f"第 {i} 张图读不到尺寸，无法确认顺序")
            continue
        if abs(pair[0] - pair[1]) > 0.02:
            problems.append(f"第 {i} 张图宽高比不一致（本地 {pair[0]:.3f} / 草稿 {pair[1]:.3f}），顺序可能变了")

    ok = not problems
    state.update(
        stage="unconfirmed" if ok else "failed",
        draft={"identity": f"title:{title}", "opened_at": _now()},
        verify={
            "ok": False,
            "machine_ok": ok,
            "image_content_order": "pending_visual_review",
            "checked_at": _now(),
            "problems": problems,
            "title": got_title,
            "chars": detail.get("chars"),
            "tags": remote_tags,
            "topic_nodes": detail.get("topic_nodes"),
            "slides": slides,
            "image_ratios": ratios,
        },
    )
    save_state(workdir, state)

    if ok:
        print("机器字段检查通过；六图内容与顺序待逐张目检，尚不能认定完整核验通过")
        print(f"  标题：{got_title}")
        print(f"  正文：{detail.get('chars')} 字（去空白）")
        print(f"  话题：{' '.join('#' + t for t in remote_tags) or '（无）'}")
        print(f"  图片：{slides} 张，尺寸已检查；相同尺寸不能证明图片内容或顺序")
        return 0

    print("核验结果：不通过，需要人工复核")
    for p in problems:
        print(f"  !! {p}")
    return 4


def main() -> int:
    parser = argparse.ArgumentParser(description="日常出稿适配脚本（只存草稿，不发布）")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("bridge-status", help="检查 Bridge / 扩展 / 登录状态")
    p1.set_defaults(func=cmd_bridge_status)

    p4 = sub.add_parser("env-probe", help="输出机器可读的环境状态 JSON")
    p4.set_defaults(func=cmd_env_probe)

    p2 = sub.add_parser("fill-new", help="新发布页：上传 6 图 + 标题 + 正文 + 话题")
    p2.add_argument("--workdir", help="本次稿件的工作目录（推荐）")
    p2.add_argument("--title-file")
    p2.add_argument("--content-file")
    p2.add_argument("--images-dir")
    p2.add_argument("--leave", action="store_true", help="填完离开编辑页以触发自动暂存")
    p2.add_argument("--dry-run", action="store_true", help="只检查输入文件，不打开浏览器")
    p2.set_defaults(func=cmd_fill_new)

    p3 = sub.add_parser("verify-draft", help="按本次标题打开对应草稿并逐项核对")
    p3.add_argument("--workdir", help="本次稿件的工作目录（推荐）")
    p3.add_argument("--title-file")
    p3.add_argument("--content-file")
    p3.set_defaults(func=cmd_verify_draft)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

