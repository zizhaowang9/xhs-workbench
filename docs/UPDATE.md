# 更新机制

## 三种文件策略
| 策略 | 含义 | 例子 |
| --- | --- | --- |
| shared | 每次更新覆盖为仓库版本（覆盖前先备份） | 程序、技能正文、公共知识库、入口脚本 |
| seed | 只在本机不存在该文件时写入，之后永不覆盖 | 首页、账号定位、已确认业务事实、执行反馈、待核实、稿件索引、系列进度、模型配置模板 |
| preserve | 从不触碰 | `config\paths.json`、`config\*.local.json`、`config\gpt_usage.jsonl`、`runs\`、`logs\`、`backups\`、`browsers\` |

## 状态文件
`<安装根>\config\update-state.json` 记录：
- `version`：已应用的版本号
- `pulled_commit`：本次 Git 实际拉取到的提交（仓库 HEAD）
- `applied_commit`：文件实际应用到安装根的提交（应用并自检通过后才写）
- `applied_at`、`last_result`（applying / ok / failed_partial_apply）、`backup_dir`

**两者必须分开看**：`git pull` 成功只说明仓库更新了，不等于工作台文件已更新成功。

## 失败与恢复
1. 更新前把将被覆盖的文件备份到 `<安装根>\backups\update-<时间戳>\`。
2. 应用或依赖失败：`last_result` 记为 `failed_partial_apply`，保留最近一次成功的 `applied_commit`；日志留在 `<安装根>\logs\`。本版不执行整体回滚，覆盖后的文件、新增文件与依赖可能处于部分应用状态；按错误修复后重新更新。备份只包含被覆盖的公共文件，不等于完整快照。
3. 遇到仓库分叉或未知本地修改：停止，不改文件，不 `push`、不 `reset --hard`、不 `clean`，提示人工处理。

## 依赖
锁文件哈希变化或没有成功同步记录时，才重新同步对应环境（`uv sync --frozen` / `pip install -r`）；否则跳过，不重装整个环境。


## 1.1.1 验证边界

更新前核对发布仓库 `zizhaowang9/xhs-workbench`、main 跟踪 origin/main、本地干净且无领先提交；程序更新只拉取，不上传个人数据。`-CheckOnly` 仅 fetch 远端信息，不合并或应用文件。

安装/接入/更新成功需要项目解释器、依赖与 Chromium 离线启动检查通过。模型 JSON 只做本地基本检查，无模型配置时明确提示待配置，不能据此声称真实调用成功。

本版优先全新安装，旧个人资料保留原位，尚未自动迁移。也没有引入受管理文件删除索引；未知个人文件不会清理，已安装版本中的已撤下公共文件需人工核对，不能声称已经自动移除。

离线回归：`python tests/offline_smoke.py`。Windows 验收：`powershell -NoProfile -ExecutionPolicy Bypass -File tests/windows_smoke.ps1 -Install`，使用全新中文空格临时安装目录，联网下载依赖后仅本地 mock 和渲染，不请求模型或小红书。GitHub Actions 主机本身可能已有 Python，不代表已证明无系统 Python 的纯净 Windows。
