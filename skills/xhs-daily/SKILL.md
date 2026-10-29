---
name: xhs-daily
description: "在小红书任务中收到开始今天的工作时，完成选题，用 GPT 写稿工具产出标题、正文、卡片文案（本机只做材料与执行），再生成六张卡片并保存真实草稿，等待人工审核和手动发布。"
---

# 小红书娱乐主播内容 · 日常出稿技能（xhs-daily）

> 本机技能，运行于 Windows「warplane」。目标：每天产出 1 篇面向娱乐主播的原创图文，
> **只做到“存入小红书草稿箱待你审核”，绝不点最终发布。**

## 0. 触发与每日默认动作
- 你说「开始今天的工作」= 自选题 → 写稿 → 出 6 张文字卡 → 目检 → 填入发布页 → 存草稿 → 草稿箱重开核验 → 登记，最后只把成品交你审稿。
- 默认节奏：**每天 1 篇，每篇 6 张卡（1 封面 + 5 正文）**。
- **文案来源（2026-10-28 起）**：标题 / 正文 / 话题 / 卡片文案 / 视频讲稿一律由 GPT 写稿工具产出（见 4.5）；本机会话只准备材料、渲染出图、填稿与核验，不擅自改写文案。
- 同一天重复收到启动指令：**先读本文件 + `knowledge\05-内容经营\03-历史作品.md` 查当天进度**，有未完成稿就续做，不重复建稿、不重复上传。
- 只有遇到 验证码 / 登录失效 / 系统授权弹窗，才停下找你；其余可逆问题自行推进。

## 1. 每次运行先读（顺序固定，全部在知识库）

**知识库根目录：`<安装根>\knowledge`（Obsidian 仓库，也是唯一有效来源）**。入口 `00-首页.md`。
`skills\xhs-daily\` 下的 `account_positioning.md`、`feedback.md`、`series\`、`posts\`、`content_library\` 已于 2026-10-29 改为指针文件，**不要在那里编辑**，改动一律进知识库。

1. `01-业务总纲\01-账号定位.md` — 账号定位、受众、可写/禁写边界。
2. `01-业务总纲\02-表达标准与你反馈.md` — 你全部历史评价与写作偏好（2026-10-24 / 10-25 / 10-27 三批，逐条标注取代关系）。
3. `01-业务总纲\04-当前有效规则.md` — 当前生效规则清单，与其他文件冲突时以它为准。
4. `03-运营知识\00-知识目录.md` — 知识总目录（A 开播准备 / B 表达与内容 / C 聊天互动 / D 观众关系 / E 复盘训练 / F 运营支持）。
   **先在这里定位 → 读条目正文 → 按条目 `依据` 回溯 `02-原始资料` 的素材摘要 → 需要原文时再读 `02-原始资料\原文\`**。不要每次重读整份原资料。
5. `05-内容经营\01-系列计划.md`、`05-内容经营\02-系列进度.md` — 本系列进度，确认今天该做第几篇。
6. `05-内容经营\03-历史作品.md` — 已发/已存草稿清单，避免重复题材与重复草稿。
7. `06-工作记录\01-当前任务.md` — 今天做到哪一步（有未完成就续做）。

读完再动手。你给的新评价：追加进 `01-业务总纲\02-表达标准与你反馈.md`（带日期与适用范围）；若属于长期规则，同步进 `04-当前有效规则.md`。

## 1.1 系列化工作模式（2026-10-27 起）
- 触发「按接话系列开始今天的工作」（或「按 XX 系列开始今天的工作」）：
  1. 按第 1 节的 7 项读知识库（定位在 `knowledge` 下，不再读 `skills` 里的旧文件）；
  2. 有未完成稿件就续做，不重复建稿；没有就选该系列下一未完成选题；
  3. 按该选题在 `knowledge\03-运营知识` 定位到的条目，再按其 `依据` 取 `knowledge\02-原始资料` 的素材摘要与原文片段（资料确实没有的写「原资料未含」）；
     - 查原文/查某个数字有没有出处，统一用 `<安装根>\tools\gpt-writer\kb_search.py "关键词"`（已做去空格与同义归一化）。
     - **没命中不等于原资料没有**：①换过同义词和中文数字 ②回查素材摘要 ③回查知识条目自己标的行号；三步都空时记「当前资料中尚未找到可支持该说法的依据」，不写「原资料没有 / 原文不存在」。
  4. 写本篇 `task.json`（主题 / 受众 / 问题 / 素材编号 / 话题方向），调 GPT 写稿工具产出 `title.txt`、`content.txt`、`cards.md`（见 4.5）；
  5. 走第 6–9 节：渲染目检 → 填发布页 → 存草稿 → 草稿箱重开核验；
  6. 核验通过后交你审核，**发布始终由你手动完成**；完成后更新 `knowledge\05-内容经营\02-系列进度.md` 与 `03-历史作品.md`。
- 按篇指定主题：你说「这篇用 sketch」→ 该篇用 `--theme sketch`，不改本文件、不改默认主题。
- 修改意见：更新对应原稿并核验，避免新增重复草稿；把适用于后续内容的意见写进 `feedback.md`，**单篇要求不擅自升级为永久规则**（确需长期生效先问你）。
- 复盘：只用你提供或工具实测的数据，缺的写「未获取」；同时记录有效咨询等招募相关反馈；不凭空断言某种写法更有效。
- 系列选题属于原创规划，不得对外描述成「已验证的小红书热点/爆款」。

## 2. 固定环境（不要重装、不改系统 PATH）
- 小红书操作仓库：`<安装根>\tools\xiaohongshu-skills`（固定提交 `b043748282a57e347c52f517dfb59819121134ab`）
  - Python：`<安装根>\tools\xiaohongshu-skills\.venv\Scripts\python.exe`
- 渲染工具仓库：`<安装根>\tools\Auto-Redbook-Skills`（固定提交 `da1c73a6624d1df1330e161663c3614753d4220b`）
  - Python：`<安装根>\tools\Auto-Redbook-Skills\.venv\Scripts\python.exe`（独立 venv，已装 markdown/PyYAML/playwright）
  - Chromium：`<安装根>\runtime\playwright`（运行渲染须设 `PLAYWRIGHT_BROWSERS_PATH` 指到这里）
- 路径配置：`<安装根>\config\paths.json`。新开 PowerShell 跑小红书仓库命令前，按它恢复进程级变量：
  `UV_PROJECT_ENVIRONMENT=...xiaohongshu-skills\.venv`、`UV_CACHE_DIR=<安装根>\cache\uv`、
  `TEMP/TMP=<安装根>\tmp`，并设 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。
- 每篇稿件独立目录：`<安装根>\runs\<北京时间yyyyMMdd-HHmmss>-draft-<英文短名>\`，内含 `title.txt`、`content.txt`、`cards.md`、`images\`。

## 3. Bridge（9333）保活与三级检查
- Bridge 是 WebSocket `ws://localhost:9333`，靠你真实 Chrome 里的「XHS Bridge」扩展连接，操作当前激活标签页。
- 先查端口：`Get-NetTCPConnection -LocalPort 9333 -State Listen`。在线就复用。
- **不在会话里用 Start-Process / 后台 Wait-Process 拉起（会随会话或 20 分钟超时被回收）。**
  可靠做法＝WMI 脱离会话启动：
  `Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='cmd /c "<安装根>\runs\bridge_run_detached.cmd"'}`
  真实监听 PID 以 `Get-NetTCPConnection` 的 OwningProcess 为准。
- 连通后用 `<安装根>\runs\check_bridge_login.py` 串行三级验证：
  `is_server_running()` → `is_extension_connected()` → `check_login_status(page)`。
- 禁止 cli check-login / 自动登录；不生成上传二维码；不读写 Cookie；不点赞/评论/私信/关注。

## 4. 选题
- 优先复用 `runs\` 已有 topic-search 产物与 `knowledge\05-内容经营\03-历史作品.md`，避免重复搜索触发风控。
- 确需新搜：串行、每词一次、图文+最多收藏+不限时间、不翻页、不加不存在的 `--limit/--page`；原始 JSON/错误/元数据落盘。
- 边界见 `knowledge\01-业务总纲\01-账号定位.md`：聚焦娱乐/颜值聊天/才艺互动主播成长；排除带货、电商培训、卖课、泛副业赚钱。
- 不把少量结果说成全站热点/已验证爆款；未打开详情就不描述封面/正文/评论；空互动写“未获取”。

## 4.5 写稿分工：GPT 出文案，本机只执行（2026-10-28 起）

- **谁写**：标题、正文、话题、6 张卡片文案（视频能力启用时再加页面要点与讲稿）由 `<安装根>\tools\gpt-writer\gpt_write.py` 实际请求 GPT 生成；本机 DeepSeek 会话只做材料准备、格式处理、渲染出图、填稿、核验。
- **不擅自改写**：只允许格式层修正（多余空格、标签换行）。要实质改稿，就把原稿要点 + 你意见写成新的修订任务交回 GPT，只改相关部分。
- **命令**（在 `<安装根>\tools\gpt-writer` 下，系统 python 即可，纯标准库）：
  ```
  python gpt_write.py --task <task.json> --run-dir <本篇目录>
  python gpt_write.py --check                       # 只自检配置，不发请求
  python gpt_write.py --task <task.json> --run-dir <dir> --mock --force   # 仅格式自查，结果必须标 mock
  ```
- **同篇不重复调用**：目录里已有 `gpt_meta.json` 且 `valid=true`、`real_call=true` 时脚本直接 `reused`；确实要重写才加 `--force`。单纯排版调整不重新调 GPT。
- **task.json 最小字段**：`topic` / `audience` / `problem` / `materials`（素材编号，可选）/ `knowledge_ids`（知识条目编号，可选，如 `["C2","D4"]`；不填则工具按 topic+problem 自动定位）/ `tags_hint` / `notes`；模板 `tools\gpt-writer\examples\task-praise.json`。
- **产物**：`title.txt`、`content.txt`（正文 + 空格分隔话题行）、`cards.md`（第 6 节渲染直接可读）、`draft.gpt.json`、`gpt_meta.json`、`video.md`（可选）。第 6–9 节流程不变。
- **密钥**：只放 `<安装根>\config\gpt.local.json` 或环境变量 `XHS_GPT_API_KEY`；不写进本文件、不写日志、不贴聊天、不导出。`provider` / `protocol` / `base_url` / `model` 同在该文件里配，官方 OpenAI 用 `responses`，其他服务商按其文档用 `chat_completions`，地址与密钥不混用。
- **多服务商切换（2026-10-29 起）**：一套服务商一份私密配置，用 `--config <文件>` 指定，互不覆盖、key 不互相搬运：
  - OpenAI：`config\gpt.local.json`（provider=openai，protocol=responses，model=gpt-6.1-sol）——额度未充值，**待验证**。
  - DeepSeek 实测通道：`config\gpt.deepseek.local.json`（provider=deepseek，protocol=responses，base_url=`https://api.deepseek.com`，model=deepseek-flash）。DeepSeek 官方支持 Responses API，端点就是 `{base}/responses`，不带 `/v1` 也能通（`/v1/responses` 同样 401 而非 404），按配置里给的不带即可。
  - 不读扣子环境变量 `DEEPSEEK_API_KEY`，也不用扣子里的任何密钥自动填这两份配置。
- **失败处理**：退出码 2＝配置不全、3＝材料或输出校验失败、4＝调用失败。三种都要保留已写好的进度并如实报告，**不得改用 DeepSeek 自己写稿后声称来自 GPT**。
  2026-10-29 实测：HTTP 429 + `insufficient_quota`/`credit_balance_exhausted` ＝ OpenAI 账户余额为 0，不是接口、地址或模型问题（key 无效会是 401）。这类错误脚本已改为不重试、直接报状态码与脱敏错误体；充值后原命令重跑即可，不改模型不改地址。
  2026-10-29 实测（DeepSeek 通道）：`--config config\gpt.deepseek.local.json` 真实调用成功，model_requested = model_returned = deepseek-flash，input 5310 / output 1720 tokens，attempts=1、degraded=[]，11.55 秒出稿，正文 359 字、0 error 0 warning；同命令再跑一次返回 `reused` 且 `gpt_meta.json` 的 response_id 不变，确认没有重复计费。**这只证明工具链路可用，不等于 GPT 已跑通。**
- **用量**：`<安装根>\config\gpt_usage.jsonl` 每次真实调用追加一行（服务商 / 请求模型 / 返回模型 / token / 篇目目录）；`gpt_meta.json` 同字段留档。
- **缺配置时**：先用 `--check` 自检、再用 `--mock` 验链路，交付时明确写「mock 格式自查通过，真实 GPT 调用待配置后验证」，不能把 mock 当 GPT 返回。

### 4.6 材料组装（2026-10-29 起，已接知识库）

写稿工具的材料不再只靠 task.json 手填，`gptw\knowledge.py` 会按下列顺序自动装配，**8 条要求逐一落地**：

1. **固定读**：`01-业务总纲` 的 01 账号定位 / 03 已确认业务事实 / 04 当前有效规则 / 02 表达标准 + `06-工作记录\01-当前任务.md`（进度）。这部分是规则，预算再紧也不裁剪。
2. **先目录后原文**：先扫 `03-运营知识` 的 frontmatter（id / 板块 / 状态 / 关键词）定位条目，再读条目正文，再按其 `依据` 取素材摘要，最后才按需从 `02-原始资料\原文\` 抠命中段落。不整份读原资料。
3. **给什么**：本篇相关知识条目（含「适用情况 / 判断要看什么」）、素材摘要、原文片段、当前有效反馈。
4. **范例单列**：`config\style_examples.json` 的 `approved` 白名单，只放你明确认可的作品；`approved` 为空时**不给范例**（`example_notes` 会写明）。
5. **排除测试稿**：白名单是显式列举，mock、`verify` 用途目录、未审核 AI 稿天然进不来；不复用「生成成功」当范例。
6. **按相关性取舍**：装配有字符预算（`limits.max_input_chars - 1200`），超预算时从「原文片段 → 素材摘要 → 知识条目」倒序削减，规则块与输出格式要求永不裁剪。
7. **留材料记录**：`materials_used.json` 落盘——固定规则各多少字、定位到的候选与打分、用了哪些条目/素材/原文片段/范例、跳过了什么、总字符与预算。
8. **生成后溯源**：`gptw\trace.py` 产出 `trace_report.json`；查红线性表述（公会政策、分成保底、第一人称带教案例、数字承诺）、查草案里是否混入「素材 N」这类内部编号、查提供的知识条目是否真的被用上。有 blocking 项时状态记 `trace_failed`（文件照写便于修），且 `trace_ok=false` 会让重跑不再 `reused`。

定位依据「关键词表 + 二字组 + 口语同义词」三路打分，`03-运营知识` 每个条目 frontmatter 都有 `关键词`，专门给换问法用。实测见 `knowledge\04-案例与训练\04-问题诊断记录.md`。

## 5. 写稿规范（以下标准同时是交给 GPT 的写作要求，工具内置同款校验）
- 标题 ≤20 字（XHS 长度口径，工具会校验）。
- **封面 title ≤5 字、subtitle ≤10 字**：professional 主题 1080 宽下主标题 151px、容器内宽 780px，5 字 755px 刚好一行；6 字必然折成 5+1（2026-10-29 实测「新人插不进话」→「新人插不进／话」）。副标题 72px，10 字 720px 到顶。这条已写进 `validate.py` 硬校验与 SYSTEM_PROMPT，超了直接判 error。
- 正文 200–400 字左右，自然具体；表达遵循 `knowledge\01-业务总纲\02-表达标准与你反馈.md` 的 2026-10-27 标准（允许教学式、直接给判断，效果表述肯定具体，可写操作带来的明确收益）；例句明确标“示例”。
- 结尾可邀请评论交流；**不写未经确认的福利/政策/收入/效果承诺；不编造你的带教案例**。
- 话题：把 `#标签` 放在 `content.txt` **最后一行**，**用空格分隔**（如 `#娱乐主播 #新人主播 #...`）。
  实测连写 `#A#B` 只会被当成 1 个标签，空格分隔才会逐条提取（最多 10 个）。fill-publish 会自动抽取末行标签并点选联想，**无需也不要重复传 `--tags`**。
  **标签必须变成可点的 `a.tiptap-topic` 话题节点**，纯文本标签等于没打。
  2026-10-28 实测根因与解法：平台联想补全只认真实键盘事件，而 Bridge 扩展的 `press_key` / `type_text` 都是 `dispatchEvent` 合成事件（isTrusted=false），Enter/Tab/Space 全部无效；唯一可行通道是用**真实鼠标**点浮层里的候选项。
  该逻辑已固化进 `publish.py` 的 `_input_single_tag` / `_click_topic_candidate`（`mouse_move` + `mouse_click`，遍历所有可见 `#creator-editor-topic-container` 找精确项），2026-10-28 本篇 7/7 全部转成话题节点。
  只有日志出现「未找到标签联想」才需人工补选；正常情况不用在页面上手动补点。

  **两行是怎么来的（2026-10-28 踩过）：** 第一次打标签时没点中联想，标签就退化成一行纯文本留在正文里；事后补标签时没有删掉这行，又在其后面新起一段重打，于是变成「一行不可点的纯文本 + 一行可点话题」。工具当时既不清旧行、也不校验结果，就静默留下了残行。
  现在 `publish.py` 的 `_input_tags` 内置四道防线，不需要手工兜：
  ① 打标签前 `_cleanup_tail_tag_lines` 清掉正文尾部已有的标签行（纯文本行、旧话题行都清）；
  ② `_activate_editor` 用真实鼠标点一下正文末尾激活编辑器，否则联想浮层根本不弹；
  ③ `_reset_last_para` + `_new_para` 单独起一段放标签（末段有正文时不清空，防误删正文）；
  ④ `_verify_tag_line` 强校验：含 `#` 的段落只能 1 行、且整行都是话题节点，不满足直接抛错，不产出半成品草稿。
  选联想项时优先点带浏览量的已有话题，避免点到「新建话题」（未审核话题保存时容易丢）。
- **卡片每页 11–13 行短句（每行 ≤12 字）**：2026-10-29 实测 6–8 行时下半页留白 40%–55%，视觉偏空。已同时把 `assets/themes/professional.css` 的正文基础字号从 42px 上调到 52px（本地补丁，auto-fit 仍会自动缩小防溢出），52px + 11–13 行可填到 85% 左右。行数与字号是一对，改一个就要复核另一个。
- 6 张卡内容与正文数字口径保持一致（避免“4个动作/6步练习”自相矛盾）。
- `cards.md` 用 UTF-8 无 BOM：YAML frontmatter（emoji/title/subtitle）出封面，正文用独立行 `---` 分 5 页。

## 6. 渲染 6 图并目检
用渲染工具自己的 venv：
```
$env:PLAYWRIGHT_BROWSERS_PATH='<安装根>\runtime\playwright'
& "<Auto-Redbook venv python>" scripts\render_xhs.py "<dir>\cards.md" --output-dir "<dir>\images" `
  --theme professional --mode auto-fit --width 1080 --height 1440 --dpr 1
```
**四个参数必须显式传全**：`--theme professional --mode auto-fit --dpr 1` 加 `--width 1080 --height 1440`。默认值是 `sketch` + `separator`，2026-10-29 漏传过一次，出来是手绘底纹且每页下方大量留白，只能重渲染。
`cards.md` 是**位置参数**，输出用 `--output-dir`；写成 `--input/--output` 会报 unrecognized arguments。
产物必须是 `cover.png` + `card_1.png..card_5.png` 共 6 张、均 1080×1440。
**逐张 read_file 目检**：中文无乱码、无溢出、阅读顺序对、字号合适、封面信息正确。有问题改 `cards.md` 重渲染，再目检。

## 7. 填入发布页（只填，绝不发布）
在小红书仓库根目录，用其 venv python：
```
python scripts/cli.py fill-publish --title-file "<dir>\title.txt" `
  --content-file "<dir>\content.txt" `
  --images "<dir>\images\cover.png" "<dir>\images\card_1.png" ... "<dir>\images\card_5.png"
```
- 图片顺序严格：**封面 cover.png 必须第一个**，其后 card_1→5。
- 看日志确认：6 张全部“上传完成”、标签“从正文末尾提取 N 个”、标题/正文长度检查通过。
- 填完立刻只读校验话题节点：`div.tiptap.ProseMirror` 内 `a.tiptap-topic` 数量应等于标签数、名称与顺序一致（本篇 7 个全中）；同时确认含 `#` 的段落数＝1。
- **严禁** `publish` / `click-publish` 或点击最终发布按钮。

## 8. 存草稿（已实测机制，重要）
- 该账号新版创作页**编辑页内没有常驻“暂存离开”按钮**，`save-draft` 直接跑会报“未找到「暂存离开」按钮”，这是正常现象，不代表内容丢失。
- 实测有效路径：**触发离开编辑页，平台自动暂存草稿**。安全做法＝用真实鼠标点左侧导航「笔记管理」（坐标用 `.d-menu-item` 文本定位后取中心，BridgePage `mouse_move`+`mouse_click`）。
  - 点前先把可能遮挡的 tippy 气泡 `display:none`。
  - 离开后不要点任何弹窗里的“放弃/不保存”；本账号实测为静默自动暂存。
- 备用：若某账号弹了确认框，只读确认弹窗里确有“暂存离开”后，点“暂存离开”，不点放弃。
- **离开前至少等 30 秒再点「笔记管理」**：平台是静默自动保存且有节流，点太快只存到中途快照（2026-10-28 实测只保留到第 4 个话题，重开后 7 个变 3 个）。保存后必须按第 9 节重开核验，不能只看退出码。
- 同一篇重复 fill-publish 会在草稿箱留下多条同名草稿，只有最新一条是成品；清理旧稿必须先取得你授权。
- 参考脚本在首篇目录：`diag_*.py`、`step_leave_menu.py`、`open_draft2.py`、`switch_image_tab.py`、`edit_draft_verify.py`。

## 9. 草稿箱重开核验（不能只看退出码）
1. 导航 `https://creator.xiaohongshu.com/publish/publish?source=official`，右上角出现 `草稿箱(N)`。
2. 真实鼠标点开 → 右侧 `.draft-drawer`，切到「图文笔记(N)」tab（默认停在“视频笔记”）。
3. 确认本篇标题、保存时间；点该篇「编辑」重新进编辑器。
4. 只读核验：标题 input 值正确；正文 contenteditable 文本完整且含末行话题；
   `div.tiptap.ProseMirror` 内 `a.tiptap-topic` 数量＝标签数（本篇 7）、名称与顺序一致；
   `.swiper-slide` 数量＝6（即 6 张图）、每张 hasImg=true；图片删除按钮 `.close-btn.hoverShow`＝6。
5. 核验通过后让页面停在该草稿编辑态，方便你直接在 Chrome 审核/手动发布。
- 注意：图文草稿存在“当前浏览器本地”，清浏览器数据会删；提醒你及时处理。

## 10. 收尾登记与交付
- 更新 `knowledge\05-内容经营\03-历史作品.md`：日期、目录、标题、选题来源、草稿核验结果（含保存时间）、状态“待你审核后手动发布”。
- 同步更新 `knowledge\05-内容经营\02-系列进度.md` 与 `06-工作记录\01-当前任务.md`、`06-工作记录\02-草稿台账.md`。
- 必要时更新项目记忆（路径/机制变化）。
- 聊天里只给 4 样：① 标题；② 6 张图实际预览（`computer://` 绝对路径）；③ 完整正文；④ 草稿已重开核验的结论 + 在小红书哪里找（创作服务平台 → 发布页 → 右上角“草稿箱” → 图文笔记）。
- 安装/日志/技术细节留在 D 盘，不堆进聊天。
- 交付前按第 4.6 第 8 条核对：`materials_used.json`、`trace_report.json` 都在本篇目录里，`trace_ok=true`。
