# 本地补丁记录（PATCHES）
生成时间：2026-10-25 19:57:08
上游仓库：https://github.com/comeonzhj/Auto-Redbook-Skills.git
基线提交：`da1c73a6624d1df1330e161663c3614753d4220b`

> 说明：下面记录的是本安装包相对上游基线提交的全部本地修改。
> 即：`tools/Auto-Redbook-Skills` 里的文件**不是**上游原版，已应用以下补丁。

## 1. 修改的文件

### `scripts/render_xhs.py`
- 原版 SHA-256：`0ee40d9c07e5d3c81ad383e2b3726b4464dcfc80e877cedf98901db9f8ff5b77`
- 本包 SHA-256：`87402eb51fafe4b0b3e4a6e2d5cdb2afabe90a874f087be4d086a13df4efae20`
- 差异行数：39

```diff
--- a/scripts/render_xhs.py (上游原版)
+++ b/scripts/render_xhs.py (本包)
@@ -34,6 +34,17 @@
 from pathlib import Path
 from typing import List, Dict, Any, Optional
 
+# --- 本地补丁（非上游）：控制台编码兜底 ---
+# Windows 默认 GBK 控制台打印 emoji 会抛 UnicodeEncodeError 导致渲染中断，
+# 这里把标准输出/错误改成 UTF-8 并允许替换无法编码的字符，
+# 保证日志里的中文与 emoji 打印不会中断渲染流程。
+for _stream in (sys.stdout, sys.stderr):
+    try:
+        _stream.reconfigure(encoding="utf-8", errors="replace")
+    except Exception:
+        pass
+
+
 try:
     import markdown
     import yaml
@@ -48,6 +59,8 @@
 SCRIPT_DIR = Path(__file__).parent.parent
 ASSETS_DIR = SCRIPT_DIR / "assets"
 THEMES_DIR = ASSETS_DIR / "themes"
+# 封面主题样式目录（本地补丁：封面与正文各自使用独立的主题样式）
+COVER_THEMES_DIR = ASSETS_DIR / "cover_themes"
 
 # 默认卡片尺寸配置 (3:4 比例)
 DEFAULT_WIDTH = 1080
@@ -142,6 +155,20 @@
         return ""
 
 
+def load_cover_theme_css(theme: str) -> str:
+    """加载封面专属主题 CSS（本地补丁）。
+
+    封面与正文页使用不同的 HTML 结构，因此单独维护封面样式目录：
+    assets/cover_themes/<theme>.css。文件缺失时返回空串，封面回退到
+    generate_cover_html 内置的基础样式，保证旧主题与旧行为不受影响。
+    """
+    theme_file = COVER_THEMES_DIR / f"{theme}.css"
+    if theme_file.exists():
+        with open(theme_file, 'r', encoding='utf-8') as f:
+            return f.read()
+    return ""
+
+
 def generate_cover_html(metadata: dict, theme: str, width: int, height: int) -> str:
     """生成封面 HTML"""
     emoji = metadata.get('emoji', '📝')
@@ -187,6 +214,11 @@
         'sketch': 'linear-gradient(180deg, #111827 0%, #6B7280 100%)',
     }
     title_bg = title_gradients.get(theme, title_gradients['default'])
+
+    # 本地补丁：加载封面专属样式（assets/cover_themes/<theme>.css）。
+    # 该样式在内联基础样式之后注入，可覆盖内层底色、圆角、阴影、
+    # 标题颜色/字重/对齐与装饰元素，实现封面级别的主题差异。
+    cover_css = load_cover_theme_css(theme)
     
     html = f'''<!DOCTYPE html>
 <html lang="zh-CN">
@@ -195,7 +227,7 @@
     <meta name="viewport" content="width={width}, height={height}">
     <title>小红书封面</title>
     <style>
-        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');
+        /* 本地补丁：封面改用系统字体栈，移除 Google Fonts 网络依赖，保证离线可渲染 */
         
         * {{
             margin: 0;
@@ -258,6 +290,8 @@
             color: #000000;
             margin-top: auto;
         }}
+        /* 本地补丁：注入封面主题样式，主题可覆盖上述基础样式 */
+        {cover_css}
     </style>
 </head>
 <body>
@@ -268,6 +302,7 @@
             <div class="cover-subtitle">{subtitle}</div>
         </div>
     </div>
+    <div class="cover-deco"></div>
 </body>
 </html>'''
     return html
```

## 2. 新增的文件

`assets/cover_themes/` 下 8 个封面主题样式（上游没有此目录）：

| 文件 | 行数 | 字节 | SHA-256 |
|---|---|---|---|
| `assets/cover_themes/botanical.css` | 68 | 1519 | `d79e685b353d489891e07895…` |
| `assets/cover_themes/default.css` | 31 | 638 | `fb2fe57105f190aec0a08316…` |
| `assets/cover_themes/neo-brutalism.css` | 69 | 1444 | `0ee35325d5ad6bac88441749…` |
| `assets/cover_themes/playful-geometric.css` | 71 | 1498 | `747adca45673587244d92389…` |
| `assets/cover_themes/professional.css` | 60 | 1242 | `7a1c4605a692ae9693929904…` |
| `assets/cover_themes/retro.css` | 64 | 1478 | `53c30016e5cd97cdec4716d6…` |
| `assets/cover_themes/sketch.css` | 87 | 2317 | `a33bd763499c7eefa23853ed…` |
| `assets/cover_themes/terminal.css` | 84 | 2067 | `cd809b08c3354c6c51112e5c…` |

## 3. 改动目的

1. **封面加载主题样式**：原版 `generate_cover_html()` 把内层卡片样式写死在函数里，8 个主题只能影响外圈渐变和 emoji，封面几乎一模一样。
   现在新增 `COVER_THEMES_DIR` 与 `load_cover_theme_css()`，在封面内联样式之后注入 `assets/cover_themes/<theme>.css`，让主题真正控制内层背景/纹理、边框圆角阴影、
   标题颜色字重对齐、留白与装饰。
2. **离线渲染**：移除封面 HTML 里的 Google Fonts `@import`，改用系统字体栈，避免无网络或内网环境渲染超时（此前实测会导致偶发 networkidle 超时）。
3. **装饰容器**：封面 body 增加 `<div class="cover-deco"></div>`，供各主题放装饰层。
4. **控制台编码兜底**：原版开头用 `print()` 输出 emoji 日志，在 Windows 默认 GBK 控制台/管道下会抛 `UnicodeEncodeError` 直接中断渲染（实测 exit 1）。现在启动时把 `sys.stdout/stderr` `reconfigure(encoding="utf-8", errors="replace")`，日志中文和 emoji 都能正常打印，不再因为打印失败而中断渲染。
5. **正文未改动**：`generate_card_html()` 与 `assets/themes/*.css` 保持上游原样。

## 4. 回滚

把 `scripts/render_xhs.py` 换回上游基线版本、删除 `assets/cover_themes/` 目录即可回到原版。
原始文件备份：`backups/cover-fix-20261025-192524/render_xhs.py.orig`（仅开发机保留，不随包分发）。

---

# 1.0.1 追加改动（相对 1.0.0 包）

> 说明：1.0.0 那一节的"本包 SHA-256"是 1.0.0 当时的哈希，1.0.1 之后以 docs/CHECKSUMS.txt 里的逐文件哈希为准。

## 上游项目的追加改动（tools/Auto-Redbook-Skills）

| 文件 | 改动 |
|---|---|
| scripts/render_xhs.py | 新增 alance_title()：封面标题按可用宽度均分，并避免标点与「的、地、得、和、与、了、着、是、在、把、被、就、都、也、而、且、以、为、对」落在行首；.cover-title 由 word-break: break-all 改为 
ormal + overflow-wrap: anywhere；删除 Google Fonts @import；正文字体栈改为本机优先（Microsoft YaHei UI / Microsoft YaHei 在前，Noto Sans SC、Source Han Sans CN、PingFang SC 兜底） |
| ssets/card.html、ssets/cover.html | 删除 Google Fonts @import，字体栈本机优先；等宽栈补 Sarasa Mono SC、Noto Sans Mono CJK SC |
| scripts/render_xhs.js、scripts/render_xhs_v2.js、scripts/render_xhs_v2.py | 同上（这两个是不在当前调用链上的备选实现，同步清理，避免以后换用时又拉外链字体） |
| ssets/cover_themes/terminal.css | 等宽字体栈补 Microsoft YaHei、Sarasa Mono SC、Noto Sans Mono CJK SC，终端主题中文不再靠西文等宽字体硬渲染 |
| ssets/cover_themes/botanical.css、
etro.css | 衬线栈补 SimSun，本机没有 Noto Serif SC 时也有中文衬线兜底 |

## 上游项目的追加改动（tools/xiaohongshu-skills）

| 文件 | 改动 |
|---|---|
| scripts/bridge_server.py | ping_server 响应新增 
oot / pid / script；新增 --root 参数；detect_repo_root() 优先返回含 config 的安装根，取不到才退回 xhs_repo。用途：让启动助手能判断"这个端口上的 Bridge 是不是本安装目录的"，而不是靠路径字符串截断比层级 |

## 本包自有文件的改动

| 文件 | 改动 |
|---|---|
| installer/common.ps1 | 新增 Resolve-InstallRoot（按脚本位置找安装根）、Get-BridgeScriptPath、Test-BridgeProbe（只读探测）、Copy-FileSafely（同内容跳过、不同则备份后覆盖）；重写 Test-BridgeOfRoot 为三态判定；Read-Config 显式按 UTF-8 读取 |
| installer/install.ps1 | 复制清单补齐 installer\、docs\、三个 .cmd、先看这里.md；用户资料改为只用缺失时初始化；paths.json 备份后合并保留自定义字段；依赖改为按锁核对；自检失败非零退出；重复安装复用已有 Python 3.12 |
| installer/start_bridge.ps1、check_env.ps1、
un_bridge.ps1 | 按自身位置解析安装根；Bridge 三态分支（复用 / 别的安装 / 归属不明）；
un_bridge 启动时把安装根传给 Bridge |
| installer/check_deps.py（新增） | 按 uv.lock / requirements 锁逐项核对，输出 JSON（ok / checked / missing / mismatch） |
| installer/bridge_probe.py（新增） | 只读连 ws 发 ping_server，回 
eachable / root / extension / pid |
| pp/adapters/common.py | 新增 pply_env()：新进程按配置恢复 TEMP / TMP / PLAYWRIGHT_BROWSERS_PATH / UV_CACHE_DIR / PYTHONUTF8 等 |
| pp/adapters/run_render.py（新增） | 渲染统一入口：先恢复环境再调 
ender_xhs.py，--print-env 可查当前进程实际环境 |
| pp/adapters/xhs_daily.py | 话题改逐字插入并读回核对；ill-new 不再谎报已保存；erify-draft 按标题定位并比对标题 / 正文 / 全部话题 / 六图顺序；新增 state.json 阶段记录；新增纯函数 compare_filled / compare_draft |
| skills/xhs-daily/SKILL.md | 补真实选题（search-feeds / get-feed-detail）、按篇指定主题、
un_render.py 渲染、--workdir 与阶段说明、核验四项与退出码、草稿入口说明 |
| 先看这里.md | 补"需要自己的扣子账号与模型"、安装目录入口用法、重装保留个人资料、草稿在创作者网页版查看 |
| docs/VERSION.md | 1.0.1 变更表与"已验证 / 待验证" |
| docs/CHECKSUMS.txt | 重新生成（1.0.1 逐文件哈希） |

