"""图文发布，对应 Go xiaohongshu/publish.go（837 行）。"""

from __future__ import annotations

import json
import logging
import random
import re
import time

from .cdp import Page
from .errors import (
    AccountRiskControlError,
    ContentTooLongError,
    PublishError,
    TitleTooLongError,
    UploadTimeoutError,
)
from .selectors import (
    CONTENT_EDITOR,
    CONTENT_LENGTH_ERROR,
    CREATOR_TAB,
    DATETIME_INPUT,
    FILE_INPUT,
    IMAGE_PREVIEW,
    ORIGINAL_SWITCH,
    ORIGINAL_SWITCH_CARD,
    POPOVER,
    PUBLISH_BUTTON,
    SCHEDULE_SWITCH,
    TAG_FIRST_ITEM,
    TAG_TOPIC_CONTAINER,
    TITLE_INPUT,
    TITLE_MAX_SUFFIX,
    UPLOAD_CONTENT,
    UPLOAD_INPUT,
    VISIBILITY_DROPDOWN,
    VISIBILITY_OPTIONS,
)
from .types import PublishImageContent
from .urls import PUBLISH_URL

logger = logging.getLogger(__name__)


def publish_image_content(page: Page, content: PublishImageContent) -> None:
    """发布图文内容（填写表单 + 点击发布）。

    Args:
        page: CDP 页面对象。
        content: 发布内容。

    Raises:
        PublishError: 发布失败。
        UploadTimeoutError: 上传超时。
        TitleTooLongError: 标题超长。
        ContentTooLongError: 正文超长。
    """
    fill_publish_form(page, content)
    click_publish_button(page)


def fill_publish_form(page: Page, content: PublishImageContent) -> None:
    """填写图文发布表单，不点击发布按钮。

    Args:
        page: CDP 页面对象。
        content: 发布内容。

    Raises:
        PublishError: 填写失败。
        UploadTimeoutError: 上传超时。
        TitleTooLongError: 标题超长。
        ContentTooLongError: 正文超长。
    """
    if not content.image_paths:
        raise PublishError("图片不能为空")

    # 导航到发布页
    _navigate_to_publish_page(page)

    # 点击"上传图文" TAB
    _click_publish_tab(page, "上传图文")
    time.sleep(1)

    # 上传图片
    _upload_images(page, content.image_paths)

    # 标签截取
    tags = content.tags[:10] if len(content.tags) > 10 else content.tags
    if len(content.tags) > 10:
        logger.warning("标签数量超过10，截取前10个")

    logger.info(
        "发布内容: title=%s, images=%d, tags=%d, schedule=%s, original=%s, visibility=%s",
        content.title,
        len(content.image_paths),
        len(tags),
        content.schedule_time,
        content.is_original,
        content.visibility,
    )

    # 填写表单（不点击发布）
    _fill_publish_form(
        page,
        content.title,
        content.content,
        tags,
        content.schedule_time,
        content.is_original,
        content.visibility,
    )


def click_publish_button(page: Page) -> None:
    """触发发布。

    XHS 把发布/暂存按钮包成 <xhs-publish-btn> Vue web component + closed shadow DOM。
    host 上挂着 'publish' 自定义事件 ——直接 dispatchEvent 比坐标点击 + CDP 真鼠标
    更可靠：不依赖坐标、不依赖 chrome.debugger、不会被反爬的鼠标事件指纹检测。

    流程：
      1. 注入 3 层响应捕获（XHR/fetch 内容匹配 + console hook + DOM toast 观察器）
      2. host.dispatchEvent(new CustomEvent('publish')) 触发发布
      3. 轮询任一层捕获到的结果，识别业务错误码（-9136 = 账号风控）

    Raises:
        PublishError: 未找到 host 或按钮被禁用。
        AccountRiskControlError: 账号被风控（如 code=-9136）。
    """
    # 1) 注入多层响应捕获
    #    XHS 自家有多层 XHR 拦截嵌套（s1-main / interceptor.js / axios），URL pattern
    #    无法可靠匹配；用"响应内容标志"判定 + console.error hook + DOM toast 观察器三管齐下。
    page.evaluate(
        """
        (() => {
            window.__xhsPublishResult = null;

            // 内容标志：成功响应含 note_id；失败响应含 HTTPBizError 或 -913x 风控码或"禁止发笔记"
            function looksLikePublishResp(body) {
                if (!body) return false;
                return body.includes('HTTPBizError')
                    || /"code":\\s*-913\\d/.test(body)
                    || body.includes('禁止发笔记')
                    || /"note_id":\\s*"[^"]+"/.test(body);
            }

            function capture(source, info) {
                if (window.__xhsPublishResult) return;  // first-wins
                window.__xhsPublishResult = {source, ...info};
            }

            function captureFromBody(source, url, status, body) {
                if (window.__xhsPublishResult) return;
                if (!looksLikePublishResp(body)) return;
                try {
                    const j = JSON.parse(body);
                    capture(source, {url, status, ...j});
                } catch (e) {
                    // body 不是顶层 JSON，尝试 regex 抽取 code/msg
                    const codeMatch = body.match(/"code":\\s*(-?\\d+)/);
                    const msgMatch = body.match(/"msg":\\s*"([^"]+)"/);
                    capture(source, {
                        url, status,
                        code: codeMatch ? parseInt(codeMatch[1], 10) : null,
                        msg: msgMatch ? msgMatch[1] : null,
                        raw: body.slice(0, 500),
                    });
                }
            }

            // Layer 1: XHR — 内容标志判定，绕开 URL pattern 不可靠的问题
            const origOpen = XMLHttpRequest.prototype.open;
            const origSend = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.open = function(method, url) {
                this.__xhsPubUrl = url;
                return origOpen.apply(this, arguments);
            };
            XMLHttpRequest.prototype.send = function() {
                this.addEventListener('loadend', () => {
                    captureFromBody('xhr', this.__xhsPubUrl, this.status, this.responseText || '');
                });
                return origSend.apply(this, arguments);
            };

            // Layer 2: fetch — 同样内容判定
            const origFetch = window.fetch;
            window.fetch = async function(...args) {
                const url = typeof args[0] === 'string' ? args[0] : args[0].url;
                const resp = await origFetch.apply(this, args);
                try {
                    const txt = await resp.clone().text();
                    captureFromBody('fetch', url, resp.status, txt);
                } catch (e) {}
                return resp;
            };

            // Layer 3: console hook — XHS publish module 失败时打印 "[发布失败] HTTPBizError: ..."
            ['error', 'log', 'warn'].forEach((method) => {
                const orig = console[method];
                console[method] = function(...args) {
                    const txt = args.map((a) => {
                        if (typeof a === 'string') return a;
                        if (a && typeof a === 'object') {
                            try { return JSON.stringify(a); } catch (e) { return String(a); }
                        }
                        return String(a);
                    }).join(' ');
                    if (txt.includes('HTTPBizError') || txt.includes('发布失败')) {
                        const codeMatch = txt.match(/"code":\\s*(-?\\d+)/);
                        const msgMatch = txt.match(/"msg":\\s*"([^"]+)"/);
                        if (codeMatch) {
                            capture('console', {
                                code: parseInt(codeMatch[1], 10),
                                msg: msgMatch ? msgMatch[1] : '发布失败',
                                raw_console: txt.slice(0, 800),
                            });
                        }
                    }
                    return orig.apply(this, args);
                };
            });

            // Layer 4: DOM MutationObserver — toast 出现"违反/违规/禁止发笔记"等关键词
            const RISK_KW = /违反|违规|禁止发笔记|审核未通过|账号异常|无法发布/;
            const obs = new MutationObserver((muts) => {
                if (window.__xhsPublishResult) return;
                muts.forEach((m) => {
                    m.addedNodes.forEach((n) => {
                        if (n.nodeType !== 1) return;
                        const txt = (n.textContent || '').trim();
                        if (txt.length === 0 || txt.length > 300) return;
                        if (!RISK_KW.test(txt)) return;
                        capture('toast', {
                            code: -9136,  // 默认风控码
                            msg: txt,
                            cls: (n.className || '').toString().slice(0, 80),
                        });
                    });
                });
            });
            obs.observe(document.body, {childList: true, subtree: true});
            window.__xhsPublishObs = obs;
        })()
        """
    )

    # 2) dispatchEvent 触发发布
    fire_result = page.evaluate(
        """
        (() => {
            const host = document.querySelector('xhs-publish-btn[is-publish="true"]');
            if (!host) return 'not_found';
            if (host.getAttribute('submit-disabled') === 'true') return 'disabled';
            host.dispatchEvent(new CustomEvent('publish', {bubbles: true, cancelable: true}));
            return 'fired';
        })()
        """
    )
    if fire_result == "not_found":
        raise PublishError("未找到 <xhs-publish-btn> 发布按钮容器")
    if fire_result == "disabled":
        raise PublishError("发布按钮 submit-disabled=true，不可发布")

    # 3) 轮询等待 publish API 响应（15s 超时）
    deadline = time.monotonic() + 15
    result = None
    while time.monotonic() < deadline:
        result = page.evaluate("window.__xhsPublishResult")
        if result:
            break
        time.sleep(0.3)

    if not result:
        logger.warning("15s 内未捕获到任何发布反馈（XHR/console/toast 都没匹配）")
        time.sleep(2)
        return

    # 4) 解析业务码
    source = result.get("source", "unknown")
    code = result.get("code")
    msg = result.get("msg", "")
    success = result.get("success")
    logger.info("捕获发布响应（来源=%s code=%s msg=%r）", source, code, msg)

    if code == 0 or success is True:
        logger.info("发布成功")
        time.sleep(2)
        return

    # XHS 风控类业务码（-913x 段）+ 关键词兜底
    is_risk_control = (
        (code is not None and -9140 <= code <= -9130)
        or "违反" in (msg or "")
        or "禁止发笔记" in (msg or "")
        or "违规" in (msg or "")
    )
    if is_risk_control:
        raise AccountRiskControlError(code or -9136, msg or "账号被风控")

    raise PublishError(f"发布失败：code={code} msg={msg!r}")


def save_as_draft(page: Page) -> None:
    """点击「暂存离开」按钮保存草稿。"""
    clicked = page.evaluate(
        """
        (() => {
            const buttons = document.querySelectorAll('button.custom-button');
            for (const btn of buttons) {
                if (btn.textContent.trim() === '暂存离开') {
                    btn.click();
                    return true;
                }
            }
            return false;
        })()
        """
    )
    if clicked:
        time.sleep(2)
        logger.info("已点击「暂存离开」，内容已保存到草稿箱")
    else:
        logger.warning("未找到「暂存离开」按钮")
        raise PublishError("未找到「暂存离开」按钮")


# ========== 页面导航 ==========


def _navigate_to_publish_page(page: Page) -> None:
    """导航到发布页面。"""
    page.navigate(PUBLISH_URL)
    page.wait_for_load(timeout=300)
    time.sleep(3)
    page.wait_dom_stable()
    time.sleep(2)


def _click_publish_tab(page: Page, tab_name: str) -> None:
    """点击发布页 TAB（上传图文/上传视频/写长文/发播客）。

    XHS 创作中心反爬升级版 —— 每个 tab 渲染 3 份：

    1. "屏外诱饵"：Vue scoped (data-v-*)，藏在 `left:-9999px; top:-9999px`，
       看起来像真 tab 但**不绑事件**，点了 active 不切换。**没有 hp 属性**所以
       老代码会把它当真 tab 误点。
    2. "明显 honey pot"：带 data-hp-kind + button-hp-installed，
       inset 在视口内但 opacity:1e-05 + z-index:-1，点了被标机器人。
    3. **真 tab**：Vue scoped + 在视口内 + 带 **data-hp-bound="1"**
       （XHS 反爬框架"已绑定真实事件"的标记）。

    正确策略：找 `data-hp-bound="1"` 且无 hp 陷阱属性的 Vue tab；用 active class
    切换确认。

    """
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        found = page.evaluate(
            f"""
            (() => {{
                const name = {json.dumps(tab_name)};
                const tabs = document.querySelectorAll({json.dumps(CREATOR_TAB)});

                // 真 tab：有 data-hp-bound + 无 hp 陷阱属性 + 在视口里
                for (const t of tabs) {{
                    if (t.hasAttribute('data-hp-kind') || t.hasAttribute('button-hp-installed')) continue;
                    if (!t.hasAttribute('data-hp-bound')) continue;
                    const title = t.querySelector('span.title');
                    if (!title || title.textContent.trim() !== name) continue;
                    const r = t.getBoundingClientRect();
                    if (r.left < -1000 || r.top < -1000) continue;
                    t.click();
                    return 'clicked';
                }}

                // 兜底 1：无 hp 陷阱属性 + 在视口内（兼容 XHS 未来去掉 data-hp-bound）
                for (const t of tabs) {{
                    if (t.hasAttribute('data-hp-kind') || t.hasAttribute('button-hp-installed')) continue;
                    const title = t.querySelector('span.title');
                    if (!title || title.textContent.trim() !== name) continue;
                    const r = t.getBoundingClientRect();
                    if (r.left < -1000 || r.top < -1000) continue;
                    t.click();
                    return 'clicked';
                }}

                return 'not_found';
            }})()
            """
        )

        # 等待 active class 切换：检查真正 active 的 tab title 是否 == 目标
        if found == "clicked":
            switched_deadline = time.monotonic() + 5
            while time.monotonic() < switched_deadline:
                active_title = page.evaluate(
                    f"""
                    (() => {{
                        // 找视口内 + 无 hp 陷阱 + active 的 tab，取它的 title
                        const tabs = document.querySelectorAll({json.dumps(CREATOR_TAB)});
                        for (const t of tabs) {{
                            if (t.hasAttribute('data-hp-kind') || t.hasAttribute('button-hp-installed')) continue;
                            if (!t.classList.contains('active')) continue;
                            const r = t.getBoundingClientRect();
                            if (r.left < -1000 || r.top < -1000) continue;
                            const title = t.querySelector('span.title');
                            return title ? title.textContent.trim() : null;
                        }}
                        return null;
                    }})()
                    """
                )
                if active_title == tab_name:
                    return
                time.sleep(0.2)
            logger.warning(
                "点击了 %s 但 active tab 仍是 %r，可能被反爬拦截", tab_name, active_title
            )

        if found == "clicked":
            return

        if found == "blocked":
            # 尝试移除弹窗
            _remove_pop_cover(page)

        time.sleep(0.2)

    # 调试：输出页面信息
    debug_info = page.evaluate("""
        (() => {
            const creatorTabs = document.querySelectorAll('div.creator-tab');
            const tabTexts = Array.from(creatorTabs).map(t => ({
                text: t.textContent.trim(),
                html: t.outerHTML.substring(0, 200)
            }));
            const url = window.location.href;
            return JSON.stringify({url, tabCount: creatorTabs.length, tabs: tabTexts});
        })()
    """)
    logger.error("调试信息: %s", debug_info)
    raise PublishError(f"没有找到发布 TAB - {tab_name}")


def _remove_pop_cover(page: Page) -> None:
    """移除弹窗遮挡。"""
    if page.has_element(POPOVER):
        page.remove_element(POPOVER)
    # 点击空位置
    x = 380 + random.randint(0, 100)
    y = 20 + random.randint(0, 60)
    page.mouse_click(float(x), float(y))


# ========== 图片上传 ==========


def _upload_images(page: Page, image_paths: list[str]) -> None:
    """逐张上传图片。"""
    import os

    valid_paths = [p for p in image_paths if os.path.exists(p)]
    if not valid_paths:
        raise PublishError("没有有效的图片文件")

    for i, path in enumerate(valid_paths):
        selector = UPLOAD_INPUT if i == 0 else FILE_INPUT
        logger.info("上传第 %d 张图片: %s", i + 1, path)

        page.set_file_input(selector, [path])
        _wait_for_upload_complete(page, i + 1)
        time.sleep(1)


def _wait_for_upload_complete(page: Page, expected_count: int) -> None:
    """等待图片上传完成。"""
    max_wait = 60.0
    start = time.monotonic()

    while time.monotonic() - start < max_wait:
        count = page.get_elements_count(IMAGE_PREVIEW)
        if count >= expected_count:
            logger.info("图片上传完成: %d", count)
            return
        time.sleep(0.5)

    raise UploadTimeoutError(f"第{expected_count}张图片上传超时(60s)")


# ========== 表单提交 ==========


def _extract_hashtags_from_content(content: str, tags: list[str]) -> tuple[str, list[str]]:
    """从正文末尾提取 hashtag 行，合并到 tags 列表。

    Returns:
        (cleaned_content, merged_tags)
    """
    lines = content.rstrip().split("\n")
    # 检查最后一行是否全是 #tag 格式
    if lines:
        last_line = lines[-1].strip()
        hashtag_pattern = re.compile(r"^(#\S+\s*)+$")
        if hashtag_pattern.match(last_line):
            # 提取 hashtag
            extracted = re.findall(r"#(\S+)", last_line)
            # 合并到 tags（去重）
            existing = {t.lstrip("#") for t in tags}
            merged = list(tags)
            for t in extracted:
                if t not in existing:
                    merged.append(t)
                    existing.add(t)
            # 去掉最后一行
            cleaned = "\n".join(lines[:-1]).rstrip()
            logger.info("从正文末尾提取 %d 个标签，合并后共 %d 个", len(extracted), len(merged))
            return cleaned, merged
    return content, list(tags)


def _fill_publish_form(
    page: Page,
    title: str,
    content: str,
    tags: list[str],
    schedule_time: str | None,
    is_original: bool,
    visibility: str,
) -> None:
    """填写表单（不点击发布）。"""
    # 从正文末尾提取 hashtag 并合并到 tags
    content, tags = _extract_hashtags_from_content(content, tags)

    # 标题——填写前先校验长度，超限直接报错（由 AI 重新生成标题）
    from title_utils import calc_title_length

    title_len = calc_title_length(title)
    if title_len > 20:
        raise TitleTooLongError(str(title_len), "20")

    page.input_text(TITLE_INPUT, title)
    time.sleep(0.5)
    _check_title_max_length(page)
    logger.info("标题长度检查通过")
    time.sleep(1)

    # 正文
    content_selector = _find_content_element(page)
    page.input_content_editable(content_selector, content)

    # 回点标题（增强稳定性）
    time.sleep(1)
    page.click_element(TITLE_INPUT)
    logger.info("已回点标题输入框")

    # 标签
    if tags:
        _input_tags(page, content_selector, tags)
    time.sleep(1)
    _check_content_max_length(page)
    logger.info("正文长度检查通过")

    # 定时发布
    if schedule_time:
        _set_schedule_publish(page, schedule_time)

    # 可见范围
    _set_visibility(page, visibility)

    # 原创声明
    if is_original:
        try:
            _set_original(page)
            logger.info("已声明原创")
        except Exception as e:
            logger.warning("设置原创声明失败: %s", e)

    logger.info("表单填写完成，等待确认发布")


def _find_content_element(page: Page) -> str:
    """查找内容输入框（兼容多种 UI）。"""
    # 2026-10 起发布页正文编辑器换成 tiptap（div.tiptap.ProseMirror），
    # 旧的 Quill 容器 div.ql-editor 已不存在，必须优先探测 tiptap。
    if page.has_element("div.tiptap.ProseMirror"):
        return "div.tiptap.ProseMirror"
    if page.has_element(CONTENT_EDITOR):
        return CONTENT_EDITOR

    # 查找带 placeholder 的 p 元素的 textbox 父元素
    found = page.evaluate(
        """
        (() => {
            const ps = document.querySelectorAll('p');
            for (const p of ps) {
                const placeholder = p.getAttribute('data-placeholder');
                if (placeholder && placeholder.includes('输入正文描述')) {
                    let current = p;
                    for (let i = 0; i < 5; i++) {
                        current = current.parentElement;
                        if (!current) break;
                        if (current.getAttribute('role') === 'textbox') {
                            return 'found';
                        }
                    }
                }
            }
            return '';
        })()
        """
    )
    if found == "found":
        return "[role='textbox']"

    raise PublishError("没有找到内容输入框")


def _check_title_max_length(page: Page) -> None:
    """检查标题长度是否超限。"""
    text = page.get_element_text(TITLE_MAX_SUFFIX)
    if text:
        parts = text.split("/")
        if len(parts) == 2:
            raise TitleTooLongError(parts[0], parts[1])
        raise TitleTooLongError(text, "?")


def _check_content_max_length(page: Page) -> None:
    """检查正文长度是否超限。"""
    text = page.get_element_text(CONTENT_LENGTH_ERROR)
    if text:
        parts = text.split("/")
        if len(parts) == 2:
            raise ContentTooLongError(parts[0], parts[1])
        raise ContentTooLongError(text, "?")


# ========== 标签输入 ==========


def _activate_editor(page: Page, content_selector: str) -> None:
    """用真实鼠标点一下正文末尾，让编辑器进入「用户交互」状态。

    实测（2026-10-28）：只靠 JS focus() 或合成 input 事件时，小红书的话题联想浮层
    #creator-editor-topic-container 不会弹出，标签只能退化成纯文本；
    先用 mouse_click（chrome.debugger 可信事件）点过编辑器末尾，联想才会正常出现。
    """
    page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return;
          const ps = [...el.querySelectorAll("p")].filter(p => (p.innerText || "").trim().length > 0);
          if (ps.length) ps[ps.length - 1].scrollIntoView({block: "center"});
        })()
        """
        % content_selector
    )
    time.sleep(0.8)
    pt = page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return null;
          const ps = [...el.querySelectorAll("p")].filter(p => (p.innerText || "").trim().length > 0);
          if (!ps.length) return null;
          const r = ps[ps.length - 1].getBoundingClientRect();
          return {x: Math.round(r.right - 12), y: Math.round(r.y + r.height / 2)};
        })()
        """
        % content_selector
    )
    if not pt:
        return
    page.mouse_move(pt["x"], pt["y"])
    time.sleep(0.3)
    page.mouse_click(pt["x"], pt["y"], "left")
    time.sleep(0.7)


def _cleanup_tail_tag_lines(page: Page, content_selector: str) -> list:
    """删掉正文尾部残留的标签行（纯文本 `#词` 行或旧话题节点行）。

    为什么需要：重复执行 fill-publish（或人工补标签）时，旧标签行不会被自动替换。
    新的一段话题节点会追加在旧纯文本标签行后面，页面上就会露出两行——
    一行不可点的纯文本、一行可点的话题。所以输入前必须先清理尾部。
    只动正文末尾连续的「标签行 / 空段」，遇到正常正文立刻停手。
    """
    return page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return [];
          const TAG_RE = /^#\\S+(\\s+#\\S+)*$/;
          const isTagLine = (p) => {
            if (p.querySelectorAll("a.tiptap-topic").length > 0) return true;
            const t = (p.innerText || "").trim();
            return t.length > 0 && t.length < 300 && TAG_RE.test(t);
          };
          const removed = [];
          for (let round = 0; round < 12; round++) {
            const ps = [...el.querySelectorAll("p")];
            if (ps.length < 2) break;
            // 尾部区：从末尾往前，遇到第一个既非标签行也非空段的段落就停
            let tailStart = ps.length;
            for (let i = ps.length - 1; i >= 0 && i >= ps.length - 12; i--) {
              const t = (ps[i].innerText || "").trim();
              if (!isTagLine(ps[i]) && t.length > 0) break;
              tailStart = i;
            }
            if (tailStart >= ps.length) break;
            let idx = -1;
            for (let i = tailStart; i < ps.length; i++) {
              if (isTagLine(ps[i])) { idx = i; break; }
            }
            if (idx <= 0) break;
            const prev = ps[idx - 1], cur = ps[idx];
            const r = document.createRange();
            r.setStart(prev, prev.childNodes.length);
            r.setEnd(cur, cur.childNodes.length);
            el.focus();
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(r);
            document.execCommand("delete", false, null);
            removed.push((cur.innerText || "").slice(0, 20));
          }
          return removed;
        })()
        """
        % content_selector
    ) or []


def _reset_last_para(page: Page, content_selector: str) -> None:
    """清空正文最后一段（通常只剩一个空段/尾巴），为标签行腾出干净的起点。"""
    page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return;
          const ps = [...el.querySelectorAll("p")];
          if (!ps.length) return {skipped: "empty"};
          const last = ps[ps.length - 1];
          // 保护：最后一段如果有实际文字，绝不能清空（会吃掉正文末段）
          if ((last.innerText || "").trim().length > 0) return {skipped: "has text"};
          el.focus();
          const r = document.createRange();
          r.selectNodeContents(last);
          const s = window.getSelection();
          s.removeAllRanges();
          s.addRange(r);
          document.execCommand("delete", false, null);
          return {ok: true};
        })()
        """
        % content_selector
    )
    time.sleep(0.5)


def _new_para(page: Page, content_selector: str) -> None:
    """在编辑器末尾新起一段，标签必须独占这一行。"""
    page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return;
          el.focus();
          const r = document.createRange();
          r.selectNodeContents(el);
          r.collapse(false);
          const s = window.getSelection();
          s.removeAllRanges();
          s.addRange(r);
          document.execCommand("insertParagraph", false, null);
        })()
        """
        % content_selector
    )
    time.sleep(0.5)


def _verify_tag_line(page: Page, content_selector: str, expected: int) -> None:
    """强校验：正文里含 # 的段落只能有 1 行，且这一行整行都是话题节点。"""
    info = page.evaluate(
        """
        (() => {
          const el = document.querySelector("%s");
          if (!el) return {};
          const hash = [...el.querySelectorAll("p")].filter(p => (p.innerText || "").indexOf("#") >= 0);
          return {
            topics: el.querySelectorAll("a.tiptap-topic").length,
            hashParas: hash.length,
            hashLineTopics: hash.length === 1 ? hash[0].querySelectorAll("a.tiptap-topic").length : -1
          };
        })()
        """
        % content_selector
    ) or {}
    topics = info.get("topics", 0)
    hash_paras = info.get("hashParas", 0)
    line_topics = info.get("hashLineTopics", -1)
    if topics != expected or hash_paras != 1 or line_topics != expected:
        raise PublishError(
            "标签行校验失败：话题节点 %d 个（应为 %d），含 # 段落 %d 行（应为 1），"
            "标签行内话题节点 %d 个（应为 %d）。请检查正文末尾是否有残留标签或被并入正文。"
            % (topics, expected, hash_paras, line_topics, expected)
        )


def _input_tags(page: Page, content_selector: str, tags: list[str]) -> None:
    """输入标签（幂等：先清尾部残留，再起干净新段重建，最后强校验只有一行）。"""
    time.sleep(1)

    # 1. 先清掉正文尾部已有的标签行。否则新增的话题行会追加在旧行后面，
    #    页面上就会露出「一行不可点的纯文本 + 一行可点的话题」两行。
    removed = _cleanup_tail_tag_lines(page, content_selector)
    if removed:
        logger.info("清理尾部残留标签行 %d 行: %s", len(removed), removed)
        time.sleep(0.5)

    # 2. 用真实鼠标点一下正文末尾激活编辑器，否则话题联想浮层不弹，标签会退化成纯文本。
    _activate_editor(page, content_selector)

    # 3. 清空末段再起新段。直接 insertParagraph 时若末段还留着内容，
    #    新段可能不会真正切开，标签会被追加到正文最后一句后面，变成「正文#标签」同一行。
    _reset_last_para(page, content_selector)
    _new_para(page, content_selector)

    for tag in tags:
        _input_single_tag(page, content_selector, tag.lstrip("#"))

    # 4. 强校验：标签必须独占一行且全部是话题节点，否则直接失败，不产出半成品草稿。
    _verify_tag_line(page, content_selector, len(tags))


def _click_topic_candidate(page: Page, tag: str, timeout: float = 6.0):
    """在可见的话题联想浮层里找到目标标签，用真实鼠标点击。

    为什么必须点鼠标：扩展的 press_key / type_text 都是 dispatchEvent 合成事件
    （isTrusted = false），ProseMirror 不响应，实测 Enter / Tab / Space 全部无法接受
    话题补全；只有 mouse_click 走 chrome.debugger 的 Input.dispatchMouseEvent，
    是可信事件，才能把 `#词` 真正转成 a.tiptap-topic 话题节点。
    另外浮层 #creator-editor-topic-container 每输入过一个标签就会残留一个容器，
    必须遍历所有「可见」容器找精确项，不能 querySelector 取第一个。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.25)
        items = page.evaluate(
            """
            (() => {
              const out = [];
              for (const c of document.querySelectorAll('#creator-editor-topic-container')) {
                if (!(c.offsetWidth || c.offsetHeight)) continue;
                for (const e of c.querySelectorAll('.item')) {
                  const r = e.getBoundingClientRect();
                  if (r.width <= 0 || r.height <= 0) continue;
                  out.push({txt: (e.textContent || '').trim(),
                            x: Math.round(r.x + r.width / 2),
                            y: Math.round(r.y + r.height / 2)});
                }
              }
              return out;
            })()
            """
        ) or []
        # 候选文本形如「#娱乐主播12.7亿浏览」或「#xx新建话题」，tag 本身不带 #。
        # 优先选带浏览量的已有话题，避免点到「新建话题」（未审核话题保存时容易丢）。
        picked = None
        for prefer_existing in (True, False):
            for it in items:
                clean = it["txt"].lstrip("#")
                if not clean.startswith(tag):
                    continue
                if prefer_existing and "浏览" not in it["txt"]:
                    continue
                picked = it
                break
            if picked:
                break
        if picked:
            page.mouse_move(picked["x"], picked["y"])
            time.sleep(0.15)
            page.mouse_click(picked["x"], picked["y"], "left")
            return picked["txt"][:30]
    return None


def _input_single_tag(page: Page, content_selector: str, tag: str) -> None:
    """输入单个标签：逐字输入后用鼠标点选联想，使其成为话题节点。"""
    page.type_text("#", delay_ms=0)
    time.sleep(0.3)
    for char in tag:
        page.type_text(char, delay_ms=0)
        time.sleep(random.uniform(0.05, 0.12))

    # 只用一次机会：重试会把 `#词` 再输一遍，末行残留成纯文本，反而更难收拾。
    picked = _click_topic_candidate(page, tag)
    if picked:
        logger.info("点击标签联想: %s -> %s", tag, picked)
    else:
        logger.warning("未找到标签联想（校验环节会报错）: %s", tag)

    # 标签之间必须补一个空格分隔：连写 #A#B 会被当成一个标签。
    page.type_text(" ", delay_ms=0)
    time.sleep(0.8)


# ========== 定时发布 ==========


def _set_schedule_publish(page: Page, schedule_time: str) -> None:
    """设置定时发布。"""
    from datetime import datetime

    # 解析 ISO8601 时间
    try:
        dt = datetime.fromisoformat(schedule_time)
    except ValueError as e:
        raise PublishError(f"定时发布时间格式错误: {e}") from e

    # 点击定时发布开关
    page.click_element(SCHEDULE_SWITCH)
    time.sleep(0.8)

    # 设置日期时间
    datetime_str = dt.strftime("%Y-%m-%d %H:%M")
    page.select_all_text(DATETIME_INPUT)
    page.input_text(DATETIME_INPUT, datetime_str)
    time.sleep(0.5)

    logger.info("已设置定时发布: %s", datetime_str)


# ========== 可见范围 ==========


def _set_visibility(page: Page, visibility: str) -> None:
    """设置可见范围。"""
    if not visibility or visibility == "公开可见":
        logger.info("可见范围: 公开可见（默认）")
        return

    supported = {"仅自己可见", "仅互关好友可见"}
    if visibility not in supported:
        raise PublishError(
            f"不支持的可见范围: {visibility}，支持: 公开可见、仅自己可见、仅互关好友可见"
        )

    # 点击下拉框
    page.click_element(VISIBILITY_DROPDOWN)
    time.sleep(0.5)

    # 查找并点击目标选项
    clicked = page.evaluate(
        f"""
        (() => {{
            const opts = document.querySelectorAll({json.dumps(VISIBILITY_OPTIONS)});
            for (const opt of opts) {{
                if (opt.textContent.includes({json.dumps(visibility)})) {{
                    opt.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
    )

    if not clicked:
        raise PublishError(f"未找到可见范围选项: {visibility}")

    logger.info("已设置可见范围: %s", visibility)
    time.sleep(0.2)


# ========== 原创声明 ==========


def _set_original(page: Page) -> None:
    """设置原创声明。"""
    # 查找原创声明卡片并点击开关
    result = page.evaluate(
        f"""
        (() => {{
            const cards = document.querySelectorAll({json.dumps(ORIGINAL_SWITCH_CARD)});
            for (const card of cards) {{
                if (!card.textContent.includes('原创声明')) continue;
                const sw = card.querySelector({json.dumps(ORIGINAL_SWITCH)});
                if (!sw) continue;
                const input = sw.querySelector('input[type="checkbox"]');
                if (input && input.checked) return 'already_on';
                sw.click();
                return 'clicked';
            }}
            return 'not_found';
        }})()
        """
    )

    if result == "already_on":
        logger.info("原创声明已开启")
        return

    if result == "not_found":
        raise PublishError("未找到原创声明选项")

    time.sleep(0.5)

    # 处理确认弹窗
    _confirm_original_declaration(page)


def _confirm_original_declaration(page: Page) -> None:
    """处理原创声明确认弹窗。"""
    time.sleep(0.8)

    # 勾选 checkbox
    page.evaluate(
        """
        (() => {
            const footers = document.querySelectorAll('div.footer');
            for (const footer of footers) {
                if (!footer.textContent.includes('原创声明须知')) continue;
                const cb = footer.querySelector('div.d-checkbox input[type="checkbox"]');
                if (cb && !cb.checked) cb.click();
                return;
            }
        })()
        """
    )
    time.sleep(0.5)

    # 点击声明原创按钮
    result = page.evaluate(
        """
        (() => {
            const footers = document.querySelectorAll('div.footer');
            for (const footer of footers) {
                if (!footer.textContent.includes('声明原创')) continue;
                const btn = footer.querySelector('button.custom-button');
                if (btn) {
                    if (btn.classList.contains('disabled') || btn.disabled) {
                        const cb = footer.querySelector('div.d-checkbox input[type="checkbox"]');
                        if (cb && !cb.checked) cb.click();
                        return 'button_disabled';
                    }
                    btn.click();
                    return 'clicked';
                }
            }
            return 'button_not_found';
        })()
        """
    )

    if result == "button_not_found":
        raise PublishError("未找到声明原创按钮")
    if result == "button_disabled":
        raise PublishError("声明原创按钮仍处于禁用状态")

    logger.info("已成功点击声明原创按钮")
    time.sleep(0.3)
