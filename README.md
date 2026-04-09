# 晓曼 Xiaoman — 智能运维助手

> 面向 DevOps / SRE 工程师的企业级 AI 运维助理，支持 RAG 知识库、MCP 工具自动化、飞书双向集成与多模态输入。

---

## 目录

- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [快速开始（本地开发）](#快速开始本地开发)
- [生产部署（Docker）](#生产部署docker)
- [功能使用指南](#功能使用指南)
  - [对话](#对话)
  - [知识库](#知识库)
  - [飞书集成](#飞书集成)
  - [LLM / Embedding / OCR 配置](#llm--embedding--ocr-配置)
  - [MCP 工具](#mcp-工具)
- [环境变量参考](#环境变量参考)
- [日志](#日志)
- [目录结构](#目录结构)

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **多轮对话** | 流式输出，支持会话历史、思考链展示、工具调用卡片 |
| **知识库 RAG** | 上传文档后自动异步分块/向量化，支持 PDF、Word、PPT、Excel、Markdown、TXT、图片（OCR） |
| **文档图片理解** | 自动提取文档内嵌图片，调用视觉模型生成描述；LLM 回答时内联引用图片 |
| **多模态输入** | 对话框支持上传图片（视觉理解）和语音录入（阿里云 ASR 转文字） |
| **飞书机器人** | WebSocket 长连接，私聊 / 群聊 @ 均可触发，默认检索所有知识库，先发占位消息再更新 |
| **联网搜索** | 基于 DuckDuckGo，可按需开启 |
| **MCP 工具** | 接入外部 MCP Server，LLM 可自主调用工具（SSE / HTTP transport） |
| **多 LLM 支持** | OpenAI、Anthropic、通义、豆包、智谱、Moonshot、DeepSeek、MiniMax、百川、自定义 |
| **日志系统** | 后端按日滚动文件日志，前端事件/错误自动上报后端 |

---

## 技术栈

**后端**

- Python 3.11 · FastAPI · SQLAlchemy (async) · SQLite / aiosqlite
- ChromaDB（向量存储） · LangChain（文本分割） · litellm（统一 LLM 调用）
- python-docx · PyPDF2 · python-pptx · openpyxl（文档解析）
- lark-oapi（飞书 WebSocket） · httpx · Pillow

**前端**

- React 18 · TypeScript · Vite · Ant Design 5
- Zustand（状态管理） · Axios · react-markdown

**基础设施**

- Docker Compose · Nginx（生产反向代理）

---

## 快速开始（本地开发）

### 前置要求

- Python 3.11+
- Node.js 20+
- Git

### 1. 克隆并配置环境

```bash
git clone <仓库地址>
cd xiaoman

# 复制环境变量模板
cp .env.example .env
```

`.env` 最少配置：

```env
SECRET_KEY=your-secret-key-here          # 任意随机字符串
ENCRYPTION_KEY=your-32-char-key-here     # 用于加密 API Key，建议 32 位随机字符串
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### 2. 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端地址：`http://localhost:8000`  
API 文档：`http://localhost:8000/docs`

### 3. 启动前端

```bash
cd frontend

npm install
npm run dev
```

前端地址：`http://localhost:5173`

### 4. 首次登录

默认管理员账号：

| 字段 | 值 |
|------|----|
| 用户名 | `admin` |
| 密码 | `admin123` |

> 建议首次登录后在系统设置中修改密码。

---

## 生产部署（Docker）

> 完整部署步骤请参阅 [DEPLOYMENT.md](./DEPLOYMENT.md)。以下为快速概要。

### 一键启动

```bash
# 1. 复制并编辑生产配置
cp .env.example .env.production
# 必填：将 ALLOWED_ORIGINS 改为服务器公网 IP
nano .env.production

# 2. 构建并启动（首次约需 5~15 分钟）
docker compose -f docker-compose.prod.yml up -d --build

# 3. 确认状态
docker compose -f docker-compose.prod.yml ps
```

访问：`http://<服务器公网IP>:8080`

### 常用运维命令

```bash
# 查看日志
docker compose -f docker-compose.prod.yml logs backend -f

# 重启服务
docker compose -f docker-compose.prod.yml restart backend

# 停止
docker compose -f docker-compose.prod.yml down

# 更新代码后重新构建
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 功能使用指南

### 对话

**基本使用**

1. 在左侧点击「新对话」创建会话
2. 在输入框中输入问题，按 **Enter** 发送（Shift+Enter 换行）
3. 点击右上角「停止」可中断流式输出

**知识库检索**

- 输入框上方的知识库选择器可多选知识库，选中后 LLM 会基于知识库内容回答
- 不选则直接使用 LLM 自身知识

**联网搜索**

- 点击「联网」按钮开启，启用后自动搜索 DuckDuckGo 并将结果注入 prompt

**附加文件（文档上下文）**

- 点击 📎 按钮上传文件（支持 PDF/Word/PPT/Excel/TXT/Markdown/图片）
- 文件内容（最多 8000 字符）会作为上下文随消息发送

**图片上传（视觉理解）**

- 点击 🖼️ 按钮上传图片（jpg/png/webp/gif/bmp，最大 10MB）
- 图片会转为 base64 发送给具有视觉能力的 LLM
- 适用场景：分析截图、解读报表图表、识别错误信息

**语音输入**

- 点击 🎤 按钮开始录音，再次点击停止
- 录音上传后由阿里云 DashScope paraformer 模型转为文字，可编辑后发送
- **无需单独配置**：自动复用系统中已配置的「通义千问」LLM 提供商的 API Key
- 若未配置通义千问，也可设置环境变量 `DASHSCOPE_API_KEY` 作为备用

**图片引用（知识库图片）**

- 当知识库中的文档包含图片（DOCX/PDF）时，LLM 回答会内联展示相关图片
- 点击图片可放大预览
- 若图片加载失败，显示图片描述文字

---

### 知识库

#### 创建知识库

进入「知识库」页面 → 点击「新建知识库」，填写：

| 字段 | 说明 |
|------|------|
| 名称 | 知识库名称 |
| Embedding 提供商 | 选择已配置的 Embedding 模型（用于向量化文本） |
| OCR 提供商 | 上传图片时使用的识别模型 |
| 分块大小 | 每个 chunk 的字符数，默认 500 |
| 分块重叠 | 相邻 chunk 的重叠字符数，默认 50 |
| Top K | 检索时返回的最相关 chunk 数量，默认 5 |

#### 上传文档

支持格式：

| 格式 | 说明 |
|------|------|
| PDF | 提取文本；安装 `pymupdf` 后可提取内嵌图片 |
| Word (.docx) | 提取文本、表格（转 Markdown）、内嵌图片（调用视觉模型描述） |
| PPT (.pptx) | 提取幻灯片文本 |
| Excel (.xlsx/.xls) | 每个 Sheet 按行分组，转 Markdown 表格 |
| TXT / Markdown | 直接分块 |
| 图片（jpg/png 等） | 调用 OCR 提取文字 |

**上传流程（异步）：**

1. 上传后文件立即保存到磁盘，接口返回 `pending` 状态
2. 后台自动开始分块 → 向量化 → 入库，状态变为 `processing` → `ready`
3. 文档列表每 3 秒自动刷新，直到所有文档完成
4. 若失败，状态显示 `错误`，悬停可查看错误信息

#### 图片与表格提取

- **DOCX 图片**：自动提取，调用默认 LLM（需支持视觉）生成中文描述（≤50字），存入知识库
- **DOCX 表格**：转换为 Markdown 格式后作为独立 chunk 存储
- **PDF 图片**：需安装 `pymupdf`（`pip install pymupdf`），否则跳过图片提取

当 LLM 回答引用了知识库中的图片时，会在回答文本中的对应位置插入图片，标记格式为 `[IMG_xxx]`。

---

### 飞书集成

#### 配置步骤

1. 进入「飞书集成」页面，填写飞书自建应用信息：

   | 字段 | 说明 |
   |------|------|
   | App ID | 飞书开发者后台 → 应用凭证 |
   | App Secret | 飞书开发者后台 → 应用凭证 |
   | Verification Token | 事件订阅页面的 Verification Token |
   | Bot Open ID | 机器人自身的 open_id（用于群聊@识别） |

2. 启用「WebSocket 长连接」模式（推荐，无需公网 IP）

3. 点击「保存」，服务自动连接飞书 WebSocket

#### 使用方式

- **私聊**：直接向机器人发送消息即可
- **群聊**：在群内 @ 机器人后跟消息内容

机器人收到消息后：
1. 立即发送「正在思考…」占位消息
2. 自动检索**所有**知识库（无需手动选择）
3. LLM 生成回答后，更新占位消息为完整回答

#### 飞书应用后台配置

需开启的权限（能力）：

- `im:message` — 读取消息
- `im:message:send_as_bot` — 发送消息
- `im:chat` — 获取群聊信息

事件订阅：

- `im.message.receive_v1` — 接收消息事件

---

### LLM / Embedding / OCR 配置

进入「模型配置」页面添加各类提供商。

#### 支持的 LLM 提供商

| 提供商 | 备注 |
|--------|------|
| OpenAI | GPT-4o、GPT-4o-mini 等 |
| Anthropic | Claude 系列 |
| 通义千问 | qwen-max、qwen-plus 等 |
| 豆包 | doubao-pro-32k 等 |
| 智谱 AI | GLM-4 系列 |
| Moonshot | moonshot-v1 系列 |
| DeepSeek | deepseek-chat、deepseek-reasoner |
| MiniMax | abab6.5 系列 |
| 百川 | Baichuan4 等 |
| 自定义 | 任意兼容 OpenAI API 的模型 |

> 启用「视觉能力」开关后，该模型可用于图片理解和文档图片描述。

#### Embedding 提供商

支持通过 litellm 调用的所有 Embedding API。常用配置：

```
提供商类型：openai
模型名称：text-embedding-3-small
API Key：sk-...
```

#### OCR 提供商

支持通过视觉模型识别图片中的文字，配置方式与 LLM 相同（需选择有视觉能力的模型）。

---

### MCP 工具

MCP（Model Context Protocol）允许 LLM 调用外部工具服务。

1. 进入「MCP 工具」页面
2. 填写 MCP Server 地址（支持 SSE 和 HTTP transport）
3. 点击「发现工具」自动获取工具列表
4. 启用后，LLM 在对话中可自主决定调用工具

**内置工具：**

- `feishu_create_group`：创建飞书群聊并拉入指定成员（飞书集成启用时自动可用）

---

## 环境变量参考

在项目根目录的 `.env` 文件中配置：

```env
# ── 必填 ──────────────────────────────────────────────────────────
SECRET_KEY=your-jwt-secret-key
ENCRYPTION_KEY=your-32-char-encryption-key

# ── CORS（开发环境默认，生产环境改为服务器 IP）─────────────────────
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]

# ── 文件存储 ──────────────────────────────────────────────────────
UPLOAD_DIR=uploads            # 上传文件存放目录
MAX_FILE_SIZE_MB=50           # 单文件最大体积（MB）

# ── 向量数据库（默认 ChromaDB，无需修改）────────────────────────────
CHROMA_PERSIST_DIR=chroma_data
USE_MILVUS=false
EMBED_MODEL=text2vec-base-chinese

# ── 语音识别备用 Key（可选）──────────────────────────────────────
# 正常情况下自动复用「通义千问」LLM 提供商的 API Key，无需设置此项
# 仅在未配置通义千问提供商时作为备用
DASHSCOPE_API_KEY=sk-...
```

### 语音识别配置说明

语音转文字使用阿里云 DashScope 的 **paraformer-v2** 模型，通过 OpenAI 兼容接口调用。

**推荐方式（无需额外配置）：**

在「模型配置 → LLM 提供商」中添加一个通义千问提供商（`provider_type = qwen`）并启用。系统会自动复用该 API Key 进行语音识别，无需任何额外设置。

**备用方式：**

若系统中没有配置通义千问提供商，在 `.env` 中设置：

```env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
```

API Key 在 [DashScope 控制台](https://dashscope.console.aliyun.com/apiKey) 创建。

---

## 日志

### 后端日志

位置：`backend/logs/`

| 文件 | 内容 |
|------|------|
| `logs/app.log` | 后端主日志（INFO 级别以上） |
| `logs/app.log.YYYY-MM-DD` | 历史滚动文件 |
| `logs/frontend/frontend.log` | 前端上报日志 |

规则：
- 按天滚动，保留最近 **7 天**
- 日志目录总大小超过 **1 GB** 时自动删除最旧文件
- 格式：`YYYY-MM-DD HH:MM:SS [LEVEL] [module] message`

### 前端日志

- 自动捕获 JS 错误（`window.onerror` / `unhandledrejection`）
- 记录用户关键操作和 API 请求耗时
- 本地 localStorage 暂存最近 **100 条**，每 **30 秒**批量上报到后端
- 网络失败时保留，下次重试

---

## 目录结构

```
xiaoman/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # 路由：auth, chat, knowledge, feishu, logs...
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic DTO
│   │   ├── services/        # 业务逻辑（chat, rag, feishu, document_parser...）
│   │   ├── core/            # 依赖注入、安全、异常处理
│   │   ├── config.py        # 环境配置
│   │   ├── database.py      # 数据库连接
│   │   └── main.py          # FastAPI 应用入口 + 日志配置
│   ├── uploads/             # 用户上传文件（含图片）
│   ├── chroma_data/         # ChromaDB 持久化数据
│   ├── logs/                # 后端日志文件
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── api/             # HTTP 客户端
│       ├── components/
│       │   ├── chat/        # ChatWindow, ChatInput, MessageBubble...
│       │   └── knowledge/   # KnowledgeBaseList, DocumentUploader...
│       ├── hooks/           # useStreamingChat
│       ├── store/           # Zustand 状态（chatStore, settingsStore）
│       ├── types/           # TypeScript 类型定义
│       └── utils/
│           ├── logger.ts    # 前端日志工具
│           └── time.ts
│
├── nginx/                   # 生产 Nginx 配置
├── docker-compose.yml       # 开发环境
├── docker-compose.prod.yml  # 生产环境
├── .env.example             # 环境变量模板
└── DEPLOYMENT.md            # 详细部署文档
```

---

## 常见问题

**Q: 文档上传后一直显示"处理中"？**

查看后端日志 `logs/app.log`，搜索 `文档分块失败`。常见原因：
- 未配置 Embedding 提供商（知识库需要 Embedding 才能向量化）
- API Key 无效或账户余额不足

**Q: 图片描述功能不工作？**

需要在「模型配置」中启用了「视觉能力」的 LLM 提供商，并将其设为默认模型。

**Q: 语音输入提示"未找到 DashScope API Key"？**

在「模型配置」中添加一个通义千问提供商并启用（provider_type = qwen），系统会自动复用该 API Key。或者在 `.env` 中设置 `DASHSCOPE_API_KEY=sk-...`，重启后端。

**Q: 飞书群聊 @ 机器人无响应？**

1. 检查飞书应用后台是否开启了「群聊消息」事件订阅
2. 在飞书配置页填写正确的 **Bot Open ID**
3. 查看后端日志中 `群聊@检查` 的输出，确认 `mention_open_ids` 中包含机器人 ID

**Q: Excel 解析报错"缺少 openpyxl 依赖"？**

```bash
pip install openpyxl
```

**Q: PDF 图片无法提取？**

默认不包含 pymupdf，需手动安装：

```bash
pip install pymupdf
```

安装后重新上传 PDF 文件即可。

---

## License

MIT
