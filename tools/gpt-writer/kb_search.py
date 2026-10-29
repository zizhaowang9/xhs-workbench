# -*- coding: utf-8 -*-
"""知识库原文检索（归一化 + 拆词 + 时长戳降权）。

为什么需要它：2026-10-29 用「15分钟」连续串去搜，漏掉了原文写的「每 15 分钟」
（数字与单位间有空格），进而把一个真实存在的资料观点误判成 AI 补充。
另外整句当关键词搜必然失配（原文不会有跟问句一模一样的句子），必须先拆词。

规则：
1. 原文先去掉所有空白再匹配，避免空格失配。
2. 查询先拆：短语（每15分钟）、数字+单位（15分钟）、内容词（自检/情绪）。
3. 同义展开：一刻钟→15分钟、半小时→30分钟、到/–/-/~/至 统一、中文↔阿拉伯数字。
4. 「15分钟34秒」这类时长戳降权，避免把视频时长当成方法频率。
5. 没命中不等于原文不存在：只输出「本次检索未找到」；多种检索方式（同义词、中文数字、去空格）及原文回查仍未找到时，记录「当前资料中尚未找到可支持该说法的依据」。
   判定前必须换过同义词、中文数字、去空格三种写法，并回查原文与摘要。

用法：
  python kb_search.py 每15分钟自检
  python kb_search.py 每隔一刻钟检查自己的情绪
  python kb_search.py 15-45秒 30秒 80%
  python kb_search.py --list
"""
from __future__ import annotations

import io
import os
import re
import sys

def _default_kb_root() -> str:
    """知识库根：XHSWORK_KNOWLEDGE / XHSWORK_ROOT，或由脚本位置推导（<根>\tools\gpt-writer）。"""
    for env in (os.environ.get("XHSWORK_KNOWLEDGE"), os.environ.get("XHSWORK_ROOT")):
        if not env:
            continue
        base = env.rstrip("\\/")
        cand = base if os.path.basename(base) == "knowledge" else os.path.join(base, "knowledge")
        if os.path.isdir(cand):
            return cand
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(os.path.dirname(os.path.dirname(here)), "knowledge")
    if os.path.isdir(cand):
        return cand
    return os.path.join(os.getcwd(), "knowledge")


ROOT = _default_kb_root()
SRC = os.path.join(ROOT, '02-原始资料', '原文')
KB = os.path.join(ROOT, '03-运营知识')

CN_NUM = {'1': '一', '2': '二', '3': '三', '4': '四', '5': '五', '6': '六',
          '7': '七', '8': '八', '9': '九', '10': '十', '15': '十五',
          '30': '三十', '45': '四十五', '60': '六十', '80': '八十'}
CN_NUM_REV = {v: k for k, v in CN_NUM.items()}

SYN = {'一刻钟': '15分钟', '半刻钟': '7分钟', '半小时': '30分钟', '一个钟头': '60分钟',
       '每隔': '每'}

UNIT_WORDS = ['分钟', '秒钟', '秒', '小时', '天', '周', '个月', '月', '轮', '次']
STOP = {'每', '个', '的', '了', '是', '在', '和', '与', '就', '都', '我', '你', '他',
        '自己', '一下', '一次', '怎么', '什么', '这个', '那个', '有没有', '能不能',
        '应该', '需要', '可以', '要', '会', '还', '也', '很', '再', '把', '给', '对',
        '检查', '说一下'}


def norm(text: str) -> str:
    return re.sub(r'\s+', '', text)


def norm_query(q: str) -> str:
    s = norm(q)
    for k, v in SYN.items():
        s = s.replace(k, v)
    for a, b in [('至', '到'), ('~', '到'), ('－', '到'), ('—', '到'), ('–', '到'), ('-', '到')]:
        s = s.replace(a, b)
    return s


def variants(q: str) -> list[str]:
    out = []
    base = norm_query(q)
    out.append(base)
    for cn, ar in CN_NUM_REV.items():
        if cn in base:
            v = base.replace(cn, ar)
            if v not in out:
                out.append(v)
    for ar, cn in CN_NUM.items():
        if re.search(r'(?<!\d)' + re.escape(ar) + r'(?!\d)', base):
            v = re.sub(r'(?<!\d)' + re.escape(ar) + r'(?!\d)', cn, base)
            if v not in out:
                out.append(v)
    return out


def terms(q: str) -> list[tuple[str, int]]:
    """返回 (词, 权重)：短语 4 > 数字+单位 3 > 内容词 2 > 裸数字 1。"""
    base = norm_query(q)
    got: dict[str, int] = {}
    # 完整词组/整句优先（2026-10-29 修）：「情绪暂停点」这类不含数字的词组，原来只被拆成
    # 3-gram/2-gram（权重 2），即使原文整词存在也永远进不了 strong，会被误标成「只算字面相关」。
    if len(base) >= 2:
        got[base] = 5
    # 区间：15到45秒 -> 15秒 / 45秒 / 15秒到45秒
    for m in re.finditer(r'(\d+)\s*到\s*(\d+)\s*(%s)' % '|'.join(UNIT_WORDS), base):
        a, b, u = m.group(1), m.group(2), m.group(3)
        got['%s%s' % (a, u)] = 3
        got['%s%s' % (b, u)] = 3
        got['%s%s到%s%s' % (a, u, b, u)] = 4
    for m in re.finditer(r'每?(\d+(?:\.\d+)?)(%s)' % '|'.join(UNIT_WORDS), base):
        whole = m.group(0)
        if whole.startswith('每'):
            got[whole] = 4
        got[m.group(1) + m.group(2)] = 3
        if len(m.group(1)) > 1:
            got[m.group(1)] = 1
    rest = re.sub(r'每?\d+(?:\.\d+)?(%s)' % '|'.join(UNIT_WORDS), '|', base)
    for c in [x for x in rest.split('|') if x]:
        if len(c) <= 3:
            if c not in STOP:
                got.setdefault(c, 2)
            continue
        for n in (3, 2):
            for i in range(len(c) - n + 1):
                w = c[i:i + n]
                if w not in STOP and all(ch not in STOP for ch in w):
                    got.setdefault(w, 2)
    return sorted(got.items(), key=lambda kv: (-kv[1], -len(kv[0])))


DUR = re.compile(r'\d+分\d+秒')


def _real_hits(n: str, w: str) -> list[int]:
    """返回该词在正文中的位置，排除「15分34秒」这种时长戳。"""
    out = []
    for m in re.finditer(re.escape(w), n):
        seg = n[m.start():m.start() + len(w) + 6]
        if DUR.search(seg) and w.endswith(('分钟', '分', '秒')) is False:
            pass
        if DUR.search(seg):
            continue
        out.append(m.start())
    return out


def load_dir(path: str, exts=('.txt', '.md')) -> dict:
    docs = {}
    if not os.path.isdir(path):
        return docs
    for dp, dn, fn in os.walk(path):
        for f in fn:
            if not f.endswith(exts):
                continue
            p = os.path.join(dp, f)
            raw = io.open(p, encoding='utf-8', errors='replace').read()
            docs[p] = (raw, norm(raw))
    return docs


def _lineno(raw: str, pos: int) -> int:
    acc = 0
    for i, ln in enumerate(raw.splitlines(), 1):
        acc += len(norm(ln))
        if acc >= pos:
            return i
    return 0


def search(q: str, docs: dict, ctx: int = 60, top: int = 4) -> int:
    print('查询：%s' % q)
    print('等价写法：%s' % ' / '.join(variants(q)))
    ts = terms(q)
    print('拆词：%s' % '、'.join('%s(%d)' % (w, wt) for w, wt in ts[:8]))
    if not ts:
        print('  本次检索未找到。')
        return 0

    scored = []
    for p, (raw, n) in docs.items():
        score = 0
        hit = []
        for w, wt in ts:
            if wt < 2 and len(w) < 2:
                continue  # 裸数字不单独当命中
            pos = _real_hits(n, w)
            if pos:
                score += wt
                hit.append(w)
        if score:
            scored.append((score, len(hit), p, raw, n, hit, ts))
    scored.sort(key=lambda x: (-x[0], -x[1]))

    strong = [s for s in scored if any(wt >= 3 and w in s[5] for w, wt in ts)]
    show = strong or scored
    if not show or all(s[0] < 2 for s in show):
        print('  本次检索未找到。')
        print('  注意：这不等于原文不存在；多种写法与原文回查仍未找到时，记为「当前资料中尚未找到可支持该说法的依据」。可再换同义词、中文/数字写法、去空格重试。')
        return 0
    if not strong:
        print('  （只命中内容词，没有命中数字/短语这类硬词，只能算字面相关，不能当依据）')
    else:
        phrase_hit = [w for w, wt in ts if wt >= 5 and any(w in s[5] for s in strong)]
        if phrase_hit:
            print('  （命中完整词组「%s」：只代表定位到原文，仍须读上下文并回查摘要；命中≠结论有依据）' % phrase_hit[0])

    for score, nhi, p, raw, n, hit, _ in show[:top]:
        print('  %s  得分 %d  命中 %d 词：%s' % (os.path.relpath(p, ROOT), score, nhi, '、'.join(hit[:6])))
        shown = 0
        for w, wt in ts:
            if w not in hit or wt < 2:
                continue
            pos = _real_hits(n, w)
            if not pos:
                continue
            m = pos[0]
            s = max(0, m - ctx)
            print('    第 %d 行 「%s」 ...%s...' % (_lineno(raw, m), w, n[s:m + ctx]))
            shown += 1
            if shown >= 2:
                break
    return len(show)


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == '--list':
        docs = load_dir(SRC)
        print('原文目录：%s（%d 个文件）' % (SRC, len(docs)))
        for p in sorted(docs):
            print('  ' + os.path.basename(p))
        return
    src = load_dir(SRC)
    kbd = load_dir(KB)
    for q in args:
        print('=' * 60)
        print('【原文】')
        search(q, src)
        print('【知识库条目】')
        search(q, kbd, ctx=40, top=3)
        print()


if __name__ == '__main__':
    main()
