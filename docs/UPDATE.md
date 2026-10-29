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
- `applied_at`、`last_result`（ok / failed）、`backup_dir`

**两者必须分开看**：`git pull` 成功只说明仓库更新了，不等于工作台文件已更新成功。

## 失败与恢复
1. 更新前把将被覆盖的文件备份到 `<安装根>\backups\update-<时间戳>\`。
2. 任一步失败：从该备份还原被覆盖的文件，`last_result` 记为 failed，日志留在 `<安装根>\logs\`。
3. 遇到仓库分叉或未知本地修改：停止，不改文件，不 `push`、不 `reset --hard`、不 `clean`，提示人工处理。

## 依赖
只有 `manifest.json` 里 `deps` 的锁文件哈希变化时，才重新同步对应环境（`uv sync --frozen` / `pip install -r`）；否则跳过，不重装整个环境。
