# xhs-workbench（团队版本仓库）

小红书工作台的程序与公共知识库。同事通过 `接入Git更新.cmd` 首次接入，之后双击 `更新工作台.cmd` 更新。

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
