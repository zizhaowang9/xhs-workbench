# xhs-workbench（团队版本仓库）

小红书工作台的程序与公共知识库。同事通过 `接入Git更新.cmd` 首次接入，之后双击 `更新工作台.cmd` 更新。

## 1.1.1 首次使用

1. 下载完整仓库 ZIP 并解压，双击 `安装.cmd`，选择安装目录；安装器下载 uv、项目 Python、两套独立依赖和渲染 Chromium。
2. 按安装完成提示在自己的 Chrome 加载随包扩展并手动登录；双击安装目录的 `启动助手.cmd`。
3. 在本机 `config/gpt.local.json` 填写自己的服务商、协议、地址、模型和密钥（模板见 `config_template/gpt.local.template.json`）。空模型会提示“程序已安装/更新、写稿模型待配置”。
4. 将安装目录的 `skills` 作为桌面 Agent 技能扫描目录，实际读新版 `SKILL.md`；填好个人定位，再开始今天的工作。成品只存草稿，人工审核和发布。

程序入口使用安装器生成的项目解释器，无需另装系统 Python。写稿正式入口 `app/adapters/run_writer.py`，渲染入口 `app/adapters/run_render.py`，路径均取自本机配置。模型配置自检不发请求；mock 明确为本地格式验证。

首次安装完成后，如需日后一键更新，安装 Git，运行解压包里的 `接入Git更新.cmd` 并选择实际安装目录；接入成功后使用安装目录的 `更新工作台.cmd`。私有仓库用自己的 GitHub 账号正常授权，具体交互取决于本机 Git 凭据设置。

旧版个人资料本轮不自动迁移；已有内容保留原位。失败恢复及验证范围见 [更新机制](docs/UPDATE.md)。

## 目录
- `tools/` 两个上游工具仓库的完整源码副本（不是嵌套 git 仓库）+ `gpt-writer`（写稿与检索）
- `app/` 适配层与依赖锁定
- `installer/` 安装、接入、更新脚本
- `skills/xhs-daily/` 技能（程序部分随版本更新）
- `knowledge/` 公共知识库（原始资料、运营知识、通用规则、训练与核验方法）
- `seed/` 个人资料模板（只在本机缺失时写入）
- `config_template/` 配置模板（不含任何密钥）
- `manifest.json` 发布清单：每个条目声明 shared（每次更新覆盖）/ seed（仅首次写入）
- `docs/` 补丁记录、来源、第三方许可证、更新机制

## 发布流程（发布端）
1. 在发布机验证：`python tools/gpt-writer/gpt_write.py --check`、`python tools/gpt-writer/kb_search.py --list`、技能能读到新版文件。
2. 改 `VERSION` 与 `manifest.json` 的 `version`，更新 `CHANGELOG.md`。
3. `git add -A` 后**逐条看 `git status` 与 `git diff --cached --stat`**，确认没有密钥、个人资料、稿件、日志。
4. `git commit -m "release: vX.Y.Z 说明"`，`git push origin main`。
5. 记录提交编号与版本号；main 只放已验证、可交付同事的版本。

## 红线
- 不提交密钥、Cookie、个人经历与业务事实、个人反馈、稿件与草稿状态、搜索原始数据、日志。
- 不把同事的个人资料写进仓库；不把某个人的确认写成通用事实。
- 不用 `push --force`、`reset --hard`、`clean` 处理更新问题。

