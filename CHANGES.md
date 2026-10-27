# 改动说明

本仓库 fork 自 [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)，遵循 Apache License 2.0。
依据协议第 4(b) 条，此处声明相对上游的修改内容。

基线版本：`3582a684`（Merge pull request #2206）

**改动规模**：12 个文件修改 + 4 个新增，合计 +625 / −230 行。

---

## 一、模型本地化：OpenAI → DeepSeek

### `gpt_researcher/config/variables/default.py`

| 配置项 | 上游默认值 | 本仓库 |
|---|---|---|
| `FAST_LLM` | `openai:gpt-4o-mini` | `deepseek:deepseek-chat` |
| `SMART_LLM` | `openai:gpt-4.1` | `deepseek:deepseek-chat` |
| `STRATEGIC_LLM` | `openai:o4-mini` | `deepseek:deepseek-chat` |
| `EMBEDDING` | `openai:text-embedding-3-small` | `custom:BAAI/bge-m3` |
| `LANGUAGE` | `english` | `chinese` |

> DeepSeek 的 API 兼容 OpenAI Chat Completions 协议，因此无需新增 provider 适配层，只需切换 base_url 与凭据。

### `gpt_researcher/llm_provider/generic/base.py`

1. **`NO_SUPPORT_TEMPERATURE_MODELS` 补充 `deepseek-reasoner`**

   上游黑名单中只有 litellm 风格的 `deepseek/deepseek-reasoner`，而实际传入的模型名是配置格式剥离后的 `deepseek-reasoner`，两者匹配不上。结果是使用推理模型时仍会携带 `temperature` 参数，服务端返回 400。

2. **`deepseek` 分支的 base_url 支持覆盖**

   ```python
   elif provider == "deepseek":
       _check_pkg("langchain_openai")
       from langchain_openai import ChatOpenAI
       llm = ChatOpenAI(
           openai_api_base=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
           openai_api_key=os.environ["DEEPSEEK_API_KEY"],
           **kwargs
       )
   ```

   原实现硬编码 base_url，无法指向自建代理或中转端点。

### `gpt_researcher/memory/embeddings.py`

`case "custom":` 分支改为使用独立的环境变量：

- `CUSTOM_EMBEDDING_API_KEY`（原复用 `OPENAI_API_KEY`）
- `CUSTOM_EMBEDDING_BASE_URL`（原复用 `OPENAI_BASE_URL`）

**原因**：切换对话模型后，`OPENAI_API_KEY` 要么为空、要么指向 Embedding 接口的 DeepSeek 端点，必然返回 401。

**同时必须保留** `check_embedding_ctx_length=False`：LangChain 的 `OpenAIEmbeddings` 默认会用 tiktoken 把文本编码成 token ID 数组再发送，仅 OpenAI 官方端点支持该格式，第三方兼容端点只接受字符串。

---

## 二、缺陷修复

### `gpt_researcher/utils/costs.py`

**问题**：非 OpenAI 模型的成本被高估约 8 倍。

**根因**：`OPENAI_MODEL_PRICING` 仅收录 OpenAI / Anthropic 模型，查表函数采用子串匹配，`deepseek-chat` 无任何命中，返回 `None` 后静默回落至 `gpt-4o-mini` 的单价。

**实测**：4000 字符输入 + 4000 字符输出，修正前 `$0.0175`，修正后按官方单价手算约 `$0.0022`。

**修复**：

- 新增 `DEEPSEEK_MODEL_PRICING`（`deepseek-chat` 0.27 / 1.10，`deepseek-reasoner` 0.55 / 2.19，单位 USD / 百万 token）
- 新增 `_get_provider_pricing`，按 provider 选择价格表
- **两条计算路径同步修改**：有 `usage_metadata` 时用真实 token 数计价；无 usage 时回退 tiktoken 估算。仅改其一会导致另一路径继续使用旧逻辑

**验证**：1000 输入 + 1000 输出 = `$0.001370`，与 `(0.27 + 1.10) / 1000` 一致。

---

## 三、运行时加固

### `main.py`

1. **监听地址收紧**

   `uvicorn.run(app, host="0.0.0.0")` → `host=os.getenv("HOST", "127.0.0.1")`，`PORT` 同样可配。

   原配置下，同一局域网内任何人访问 `IP:8000` 均可无鉴权提交研究任务，消耗 API 额度。

   > 对 Docker 无影响：`Dockerfile` 中为 `ARG HOST=0.0.0.0` 且 CMD 直接调用 uvicorn，不经过 `main.py` 的 `__main__` 分支。

2. **日志轮转**

   `logging.FileHandler('logs/app.log')` → `RotatingFileHandler('logs/app.log', maxBytes=10MB, backupCount=5, encoding='utf-8')`

   原实现单文件无限追加；未指定 encoding 时 Windows 默认 GBK，写入中文会抛 `UnicodeEncodeError`。

### `backend/server/app.py`

PDF 导出失败降级：`write_md_to_pdf` 包裹 `try/except`，捕获后仅记录 warning。

**原因**：Windows 缺少 GTK 运行库时，`weasyprint` 抛出 `OSError: cannot load library 'libgobject-2.0-0'`，原实现会将整个研究请求打断——报告已生成但用户拿不到。

**注意**：这只是降级，PDF 导出在无 GTK 环境下仍不可用。彻底解决需安装 GTK 或改用无系统依赖的导出方案（如 `xhtml2pdf`）。

### 其他

- `.env.example`：补充 DeepSeek / 嵌入 / HOST / PORT 配置块与注释；移除误提交的真实密钥
- `.gitignore`：新增 `*.bak`、`.env.deepseek.template`、`fix_env.bat`、`frontend/apologize.*`
- `.python-version`：`3.12.1` → `3.14.7`，与 `Dockerfile` 的 `python:3.14` 一致
- 新增 `requirements.lock.txt`：`pip freeze` 生成的 180 行精确版本，用于复现环境。`requirements.txt` 保持宽松以跟进上游

---

## 四、前端

### 界面汉化

`frontend/index.html` 与 `frontend/scripts.js` 共 172 处文案中文化，覆盖首屏、表单、进度面板、报告操作栏、历史记录、MCP 配置与全部 toast 提示。

**刻意保留英文**（改动会导致功能失效）：

- 所有 `value=` 属性值：`research_report`、`detailed_report`、`web`、`local`、`hybrid`、`azure`、`newest`、`oldest`，以及 15 个语气枚举。后端以 `Tone[research_request.tone]` 按值索引，改动会抛 `KeyError`
- `id` / `class` / `data-preset`
- `console.*` 调试输出（不对用户可见）

`localize_frontend.py` 为可重复执行的汉化脚本，用于 `git pull` 上游更新后恢复汉化。

### Stripe 风格改版

**采用覆盖层方案，不修改原 `styles.css`（2369 行）：**

- 新增 `frontend/stripe-theme.css`（1499 行），在 `styles.css` 之后加载
- 新增 `frontend/stripe-ui.js`（319 行）

理由：可整层回滚（删一行 `<link>` 即恢复原样式）、不干扰上游更新、样式与逻辑隔离。

**视觉**：浅色渐变光晕背景 + 细网格、渐变标题、Stripe 紫主按钮、24px 圆角卡片、毛玻璃固定导航。

**动效**：按钮涟漪（事件委托）、悬停上浮、按下回弹、提交加载态、滚动入场、完成高亮。

**功能保障**：改版前提取 `scripts.js` 依赖的全部选择器（55 个 `getElementById` + 12 个 `querySelector`）并逐一核对，确认无遗漏。

### 完成提示音

- 触发点：`scripts.js` 中 `data.type === 'path'` 分支，新增一行 `window.__onResearchComplete()` 钩子
- 音频文件缺失时，回退至 Web Audio API 合成的上行和弦琶音
- 首次用户点击时解锁 `AudioContext`，规避浏览器自动播放策略
- 右下角提供开关，状态写入 localStorage（读写均包裹 try/catch，规避隐私模式异常）

> 因版权原因，`frontend/apologize.*` 不随仓库分发，已加入 `.gitignore`。

---

## 五、未改动范围

核心研究链路（任务规划、检索、抓取、上下文压缩、报告生成）、`multi_agents/` 多智能体模式、`evals/`、上游测试套件均未修改。

**回归验证**：以 `git worktree` 检出上游基线 `3582a684` 做对照，同一依赖环境下运行完整测试套件：

| | 本仓库 | 上游基线 |
|---|---|---|
| 结果 | 30 失败 / 544 通过 | 30 失败 / 544 通过 |
| 失败用例集合 | — | `diff` 完全一致 |

结论：改动未引入回归。那 30 个失败为上游既有问题（测试间状态污染导致顺序性失败，单独运行其中 28 个可通过）。

---

## 六、已知问题

| 问题 | 状态 | 说明 |
|---|---|---|
| PDF 导出不可用 | 未解决 | Windows 缺 GTK，仅做了降级处理 |
| 服务无鉴权 | 未解决 | 已通过监听 127.0.0.1 降低风险，公网部署需自行添加 API key 中间件与限流 |
| 测试未做 mock 隔离 | 未解决 | 有效密钥下运行测试会真实调用外部 API，耗时从 22s 增至 170s 并产生费用 |
| `requirements.txt` 未锁版本 | 部分缓解 | 另附 `requirements.lock.txt`，原文件保持上游风格 |
| 报告输出受 8K token 上限约束 | 未解决 | `deepseek-chat` 硬限制，`TOTAL_WORDS` 建议不超过 3000 |
