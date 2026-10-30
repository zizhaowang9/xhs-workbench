---
name: xhs-daily
description: "收到开始今天的工作时，续做已有进度或选题，调用配置好的写稿工具，渲染六图，保存草稿并重开核验，交人工审核和手动发布。"
---

# 小红书日常图文工作台

## 1. 工作边界与续做

默认每天 1 篇，每篇 6 张卡（1 封面 + 5 正文）。只保存草稿，最终发布由用户手动完成。禁止调用 `publish`、`click-publish` 或点击最终发布按钮。禁止自动登录、导出 Cookie、上传二维码、点赞、评论、私信、关注。

同日重复启动、跨日再次启动、修改稿件时，先读经营记录和当前任务，找到稿件目录与当前步骤。有未完成稿先续做；已有当天成品则交用户审稿。先核对已有草稿，避免重复建稿、重复上传、重复计费。遇到登录失效、验证码或系统授权才暂停；其他可逆问题自行处理并记录。旧稿清理需用户明确授权。

文件更新只证明磁盘内容已变；只有实际读取后才能说 Agent 已加载新版规则。

## 2. 每次先读

`<安装根>` 从本机 `config\paths.json` 获取。知识库以其中的 `knowledge_dir` 为准，默认 `<安装根>\knowledge`。依次读取：

1. `00-首页.md`。
2. `01-业务总纲\01-账号定位.md`、`03-已确认业务事实.md`、`04-当前有效规则.md`。
3. `01-业务总纲\02-表达标准与反馈.md`（公共标准）与 `04-案例与训练\03-执行反馈.md`（本机个人反馈）。
4. `05-内容经营\01-系列计划.md`、`02-系列进度.md`、`03-历史作品.md`。
5. `06-工作记录\01-当前任务.md`、`02-草稿台账.md`。
6. `03-运营知识\00-知识目录.md`；按本篇问题定位条目，读正文，再按“依据”回查 `02-原始资料` 摘要和必要原文片段。

新用户定位空白时先确认定位，不能编造业务事实。用户反馈追加到个人 `04-案例与训练\03-执行反馈.md`，标日期、适用范围、取代关系；单篇要求不能自动升级为永久规则。公共文件会更新覆盖，个人反馈不要写进公共表达标准文件。

本版不自动迁移旧版 `skills\xhs-daily` 的个人文件。已有旧资料仍保留原位；不能声称其已迁移、已变成指针或已进入新模型材料。若用户要求继续旧任务，先核对原记录与新知识库，缺口如实说明。

## 3. 正式运行入口

用 PowerShell 读取本机配置；命令示例中的 `$Root`、`$Run` 须换成本机实际路径。所有 Python 命令都用项目解释器，不能假设系统安装了 Python。两个虚拟环境保持独立，不重装系统、不改全局 PATH。

```powershell
$Root = '<安装根>'
$Paths = Get-Content -LiteralPath (Join-Path $Root 'config\paths.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$XhsPy = $Paths.xhs_python
$RenderPy = $Paths.render_python
$Run = '<本篇稿件目录>'
. (Join-Path $Root 'installer\common.ps1')
Set-ProjectEnv $Root
```

- 安装/修复：安装根的 `安装.cmd`；复查：`检查环境.cmd`；启动 Bridge：`启动助手.cmd`（保留其独立窗口）。不要依赖 `runs` 内开发机临时脚本。
- Bridge 状态：`& $XhsPy "$Root\app\adapters\xhs_daily.py" bridge-status`。它检查服务、扩展和登录。端口和地址从本机配置恢复，不硬写其他路径。运行前由用户在自己的 Chrome 加载随包扩展并手动登录。
- writer：`app\adapters\run_writer.py`；render：`app\adapters\run_render.py`。这两个正式入口读取路径配置，恢复 TEMP/TMP、uv 缓存和 Chromium 路径。Chromium 以 `paths.playwright_browsers` 为准，默认 `<安装根>\browsers`。
- 稿件独立目录：`runs\<北京时间yyyyMMdd-HHmmss>-draft-<英文短名>`，保存任务、原稿、图片和状态。不要把稿件、个人配置、密钥、日志上传到程序 Git 仓库。

## 4. 取材与写稿

优先用已有选题搜索结果和历史，减少重复搜索。新搜索串行、每词一次，不翻页、不加 CLI 未提供的参数。筛选娱乐/颜值聊天/才艺互动主播成长内容，排除带货、电商培训、卖课和泛副业赚钱。每次新进程调用 CLI 前恢复项目环境并进入配置的仓库目录：

```powershell
. (Join-Path $Root 'installer\common.ps1')
Set-ProjectEnv $Root
Push-Location -LiteralPath $Paths.xhs_repo
try {
  & $XhsPy scripts\cli.py search-feeds --keyword '新人娱乐主播聊天' --sort-by '最多收藏' --note-type '图文' --publish-time '不限'
  # 只使用本次搜索真实返回的 feed_id 与 xsec_token，不猜造：
  & $XhsPy scripts\cli.py get-feed-detail --feed-id '<真实feed_id>' --xsec-token '<真实xsec_token>'
} finally { Pop-Location }
```

搜索和详情的原始结果、错误及时间元数据写入本次稿件目录；只对筛选后确实需要的笔记调用详情。未打开详情就不能描述封面、正文或评论；无数据写“未获取”。系列选题属于原创规划，不能称为已验证热点或爆款。

查原文用项目 Python：

```powershell
& $XhsPy "$Root\tools\gpt-writer\kb_search.py" '关键词'
```

没命中不等于原文没有：换同义词和中文数字，回查素材摘要、条目所标依据或行号。仍未找到时写“当前资料中尚未找到可支持该说法的依据”。不得编造政策、收入、案例或数字承诺。

标题、正文、话题和六卡文案由配置好的写稿服务实际生成。本机会话只准备材料、处理格式、渲染、填稿、核验；实质修改交回写稿工具，不能冒充模型输出。服务商、协议、地址、模型与密钥都来自用户本机配置，不能将某个账号的余额或某次服务商测试当作通用事实。

日常写稿仅在配置建立或变更时先运行一次 `--check`，之后直接真实写稿，不先在正式稿件目录运行 mock。先写本篇 `task.json`，最小字段 `topic`、`problem`；可含 `audience`、`materials`、`knowledge_ids`、`tags_hint`、`notes`。参考 `tools\gpt-writer\examples\task-praise.json`。配置、mock与真实调用分开：

```powershell
& $XhsPy "$Root\app\adapters\run_writer.py" --check
# 用户已配置并授权实际出稿时：
& $XhsPy "$Root\app\adapters\run_writer.py" --task "$Run\task.json" --run-dir $Run
```

`--check` 只检查配置，不代表真实服务可用。只有单独验收时才使用 `--mock --run-dir <独立mock目录>`，不能与正式稿共用目录；mock 必须标为格式自查，不能交作真实模型稿。多服务商用 `--config <本机配置>` 分开。密钥不写入技能、日志或聊天。

有效真实稿可复用；确实需要重写才用 `--force`，单纯排版不重复付费调用。退出码 2/3/4 分别对应配置、校验、调用失败，记录进度并如实报告。核对 `materials_used.json`、`trace_report.json` 和 `gpt_meta.json`；溯源失败须修正，不能伪称通过。模型材料固定包含个人执行反馈、经营历史和当前任务。

## 5. 六卡与渲染

标题 ≤20 字；封面主标题 ≤5 字、副标题 ≤10 字。正文约 200–400 字，自然具体，示例明确标“示例”，不编造带教经历。末行话题以空格分隔、最多 10 个；页面中必须变成实际话题节点。

卡片共六张，内容与正文数字口径一致。`cards.md` 用 UTF-8 无 BOM；frontmatter 生成封面，正文用独立行 `---` 分五页。正文卡片每页 11–13 行短句，每行 ≤12 字；有溢出先改稿并重新渲染目检。

```powershell
& $RenderPy "$Root\app\adapters\run_render.py" --cards "$Run\cards.md" --output-dir "$Run\images" --theme professional --mode auto-fit --width 1080 --height 1440 --dpr 1
```

用户说“这篇用 sketch”则本篇参数用 `--theme sketch`，不改默认主题。产物必须为 `cover.png`、`card_1.png` 至 `card_5.png`，均 1080×1440。逐张查看实际图片，检查中文、溢出、顺序、字号、封面和正文内容。

## 6. 填稿、保存与重开

先核对稿件记录与草稿台账。新稿默认使用有状态的正式适配入口：

```powershell
& $XhsPy "$Root\app\adapters\xhs_daily.py" fill-new --workdir $Run --leave
```

已有 draft identity、进行中状态或失败尝试时，继续原稿并先重开核验，不重复建稿。`--leave` 仅尝试离开触发暂存，不是可靠保存证明，后续仍须重开。只有已确认当前页面和稿件状态、确需处理适配器无法执行的问题时，才可用底层 CLI `fill-publish` 作为 fallback；每次调用先 dot-source `installer\common.ps1`、执行 `Set-ProjectEnv $Root`，再 `Push-Location $Paths.xhs_repo`，完成后 `Pop-Location`，同步维护同一稿件的状态。不能绕开防重建判断，盲目重跑 CLI 创建第二份。

图片顺序必须封面第一、card_1→5。核对六张上传完成，标题/正文读回正确，话题名称、数量、顺序与原稿一致；适配器在无匹配联想时可能暂留纯文本话题，这是未完成的降级状态。最终核验要求话题转成可点节点，否则脚本会拒绝通过；应在原稿中修正，不能为补话题另建稿。末尾不能重复残留纯文本话题行。

保存机制以当前页面实际控件为准。随包 CLI 提供 `save-draft`，只有页面确实存在相应按钮才使用；没有时，等待至少 30 秒，再用实际可见的“笔记管理”等导航触发离开，让平台暂存。遇到确认框只选明确的“暂存离开”，不能点放弃。不得把某个账号的静默自动保存行为当成所有账号通用。离开、退出码或出现草稿数都不能单独证明保存完整。

使用正式入口重开匹配标题的草稿并比对：

```powershell
& $XhsPy "$Root\app\adapters\xhs_daily.py" verify-draft --workdir $Run
```

该脚本只检查标题、正文、话题节点、六图数量和尺寸。**相同宽高比不能证明图片内容与顺序正确**。必须实际查看重开草稿的每张图片，与本地六图逐张比对内容和顺序；全部一致后才可登记完整核验通过。无需每步找用户确认，Agent 能查看时自行目检；无法查看时明确留下“图片内容/顺序待核验”，不能报完整通过。标题相同但多条草稿时，结合保存时间识别，不能盲选旧条目。

通过后让页面停在该草稿编辑态供用户审核和手动发布。草稿可能保存在当前浏览器本地，避免清理浏览器数据。

## 7. 登记与交付

同步更新 `05-内容经营` 的进度、历史，`06-工作记录` 的当前任务和草稿台账，记录日期、目录、标题、步骤、保存时间、机器检查和图片目检结论，状态写“待人工审核后手动发布”。未完成状态要可供下次继续；未经用户确认发布不能记为已发布。

交付标题、六张实际图片预览、完整正文及核验结论，说明草稿位置（创作服务平台 → 发布页 → 草稿箱 → 图文笔记）。技术细节留在稿件与日志中；mock、缺配置、未真实运行或未目检的限制必须明说。
