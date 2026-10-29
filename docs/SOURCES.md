# 来源清单

| 目录 | 来源 | 提交 | 许可 |
|---|---|---|---|
| `tools/xiaohongshu-skills` | https://github.com/autoclaw-cc/xiaohongshu-skills.git | `b043748282a57e347c52f517dfb59819121134ab` | MIT |
| `tools/Auto-Redbook-Skills` | https://github.com/comeonzhj/Auto-Redbook-Skills.git | `da1c73a6624d1df1330e161663c3614753d4220b` | MIT（见 README 声明） |

其他运行时来源（安装时下载，不随包分发）：

- uv：https://github.com/astral-sh/uv/releases（下载到 `安装目录\bin`）
- Python 3.12：由 uv 下载到 `安装目录\runtime\python`
- Playwright Chromium：由 `python -m playwright install chromium` 下载到 `安装目录\browsers`
- 渲染与项目依赖：PyPI（版本固定在 `app/constraints/render-requirements.lock.txt` 与 `tools/xiaohongshu-skills/uv.lock`）
