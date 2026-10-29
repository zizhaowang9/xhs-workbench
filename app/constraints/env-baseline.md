# 环境基线（本次打包实际验证通过的组合）

| 项目 | 值 |
|---|---|
| 操作系统 | Windows 10 / 11（x64） |
| Python | 3.12.10（安装器用 uv 装到 安装目录\runtime\python） |
| uv | 0.11.11（安装时检测复用，缺失则下载到 安装目录\bin\uv.exe） |
| 渲染依赖 | 见 render-requirements.lock.txt（6 个包，全部固定版本） |
| 小红书项目依赖 | 随包 uv.lock（uv sync --frozen 安装） |
| 渲染浏览器 | Playwright Chromium，装在 安装目录\browsers |
| 出图规格 | 1080×1440，DPR=1，PNG |

说明：渲染项目上游 pyproject 只声明了部分依赖，实际出图还需要 greenlet / pyee / typing_extensions
等传递依赖，因此这里用锁定清单一次装齐，避免版本漂移导致版式差异。