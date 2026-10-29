# GPT 写稿工具（xhs-daily 配套）

只做一件事：**把一篇稿件的写作任务交给 GPT，把结果落成现有渲染/填稿工具能直接读的文件。**
不碰 Bridge、不碰草稿、不改任何现有工具，也不改写小红书账号资料。

## 1. 分工

| 环节 | 谁做 |
|---|---|
| 准备材料（定位、规则、素材片段、历史示例） | 本机（DeepSeek 会话 / 脚本） |
| 标题、正文、话题、6 张卡片文案（+ 视频要点与讲稿） | **GPT**（本工具实际请求） |
| 格式处理、渲染出图、填发布页、核验 | 本机（DeepSeek 会话） |

本机不擅自改写 GPT 文案。需要实质改稿时，把原稿 + 修改意见交回 GPT，只改相关部分。

## 2. 首次配置（只做一次）

编辑 `<安装根>\config\gpt.local.json`（本机私密文件，不在技能目录里）：

```json
{
  "provider": "openai",
  "protocol": "responses",
  "base_url": "https://api.openai.com/v1",
  "model": "填服务商实际模型 ID",
  "api_key": "填该服务商的密钥",
  "api_key_env": "XHS_GPT_API_KEY",
  "json_mode": "json_schema"
}
```

要点：

- **官方 OpenAI → `protocol: "responses"`**（优先用 Responses API）。
- **其他服务商 → 按其文档填 `chat_completions`**，`base_url` 用该服务商自己的地址。
  地址和密钥必须来自同一家，**不要混用**。
- 不想写进文件，也可以设环境变量 `XHS_GPT_API_KEY`，配置文件里的 `api_key` 留空即可。
- 密钥不会出现在日志、`gpt_meta.json`、技能正文或任何导出物里；脚本只打印掩码（如 `sk-a...1234`）。
- `json_mode`：`json_schema`（默认，最稳）→ 服务商不支持会依次降级到 `json_object`、无约束，降级记录写在 `gpt_meta.json` 的 `degraded` 里。

自检（不发请求）：

```
cd <安装根>\tools\gpt-writer
python gpt_write.py --check
```

## 3. 日常用法

```
# 正式写稿
python gpt_write.py --task <task.json> --run-dir <本篇目录>

# 已经写过就复用（脚本自动判断，也可以显式 --check 看材料）
python gpt_write.py --task <task.json> --run-dir <本篇目录>

# 本地格式自查（明确 mock，不能当 GPT 返回）
python gpt_write.py --task <task.json> --run-dir <dir> --mock --force

# 需要视频要点与讲稿（前提：视频能力已安装）
python gpt_write.py --task <task.json> --run-dir <dir> --video
```

任务文件字段（`examples/task-praise.json` 可复制）：

| 字段 | 说明 |
|---|---|
| `topic` | 本篇主题（必填） |
| `audience` | 目标受众 |
| `problem` | 要解决的问题（必填） |
| `materials` | 内容库素材编号数组，如 `["10","11","2/3"]` |
| `tags_hint` | 建议话题方向 |
| `notes` | 本篇额外要求 |

## 4. 产物

写在 `<run-dir>` 下，和手工写稿的结构完全一致：

- `title.txt`
- `content.txt`（正文 + 空行 + 空格分隔的 `#话题` 行）
- `cards.md`（YAML frontmatter + 5 页，`---` 分隔，`render_xhs.py` 直接可读）
- `draft.gpt.json`（GPT 原始结构，追溯用）
- `gpt_meta.json`（服务商、协议、请求模型、返回模型、token 用量、校验结论、降级记录）
- `video.md`（仅 `--video` 且有视频能力时）

## 5. 用量与重试

- 每篇默认只发一次请求。
- `limits.max_output_tokens` 默认 3500，`max_retries` 默认 2（只对 429/5xx/网络错误重试，带退避）。
- 每次真实调用追加一行到 `<安装根>\config\gpt_usage.jsonl`：时间、服务商、模型、token、篇目目录。
- 输入超过 `limits.max_input_chars`（默认 24000）会截断材料并记录 `truncated`。

## 6. 失败与退出码

| 退出码 | 含义 | 处理 |
|---|---|---|
| 0 | 成功，或已有成功稿件被复用 | 继续渲染/填稿 |
| 2 | 配置不完整（缺 model / api_key 等） | 按提示补 `gpt.local.json`，**不要**改用本机模型代写 |
| 3 | 材料或输出校验失败 | 看 `gpt_result.json` 的 errors；实质性重写才加 `--force` 重新调用 |
| 4 | GPT 调用失败 | 进度已保留，如实报告卡点，不静默改用 DeepSeek |

校验不通过时**不会**生成 `title.txt/content.txt/cards.md`，只留 `draft.gpt.json` 方便排查，避免半成品流入渲染与草稿。
