# 晓曼 (Xiaoman) - AI 运维助理

> 面向 DevOps/SRE 工程师的企业级 AI 运维助理平台，集成 RAG 知识库、MCP 工具自动化、多大模型接入与飞书通知。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Node](https://img.shields.io/badge/node-18%2B-green)

---

## 功能特性

- **多轮对话** — 现代化运维对话界面，支持文字与文件输入，流式输出
- **RAG 知识库** — 上传 PDF / Word / PPT / 图片，自动解析入库，智能检索
- **Skill 路由** — 根据意图自动分发至知识问答、MCP 工具执行或直接对话
- **MCP 工具集成** — 对接标准 MCP 协议，一键触发 Runbook 或日志分析
- **多大模型支持** — 兼容 OpenAI、Anthropic、DeepSeek、通义千问、文心一言、智谱、Moonshot、豆包、MiniMax、百川等 10+ 主流模型
- **飞书集成** — 接收告警、推送诊断报告（P1）
- **暗色模式** — 支持亮色 / 暗色主题切换

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + SQLAlchemy 2.0 (async) |
| 数据库 | SQLite（开发） / PostgreSQL（生产） |
| 向量数据库 | Milvus（可选，默认关闭） |
| LLM 抽象 | LiteLLM |
| 前端框架 | React 18 + TypeScript + Vite |
| UI 组件库 | Ant Design 5 + Tailwind CSS |
| 状态管理 | Zustand |
| 容器化 | Docker + Docker Compose |

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- pip / npm

### 1. 克隆项目

```bash
git clone https://github.com/kongxinshitou/xiaoman.git
cd xiaoman
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少修改以下字段：

```env
# 必填：JWT 签名密钥（任意随机字符串）
SECRET_KEY=your-secret-key-change-this

# 可选：若已有 LLM API Key，可在此预配置；也可登录后在界面中添加
# 后续可在「设置 → 大模型配置」中随时添加/切换
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

首次启动会自动：
- 创建 SQLite 数据库（`xiaoman.db`）
- 初始化默认技能（RAG 检索、MCP 执行、直接对话）
- 创建默认管理员账号

### 4. 启动前端

新开一个终端：

```bash
cd frontend
npm install
npm run dev
```

### 5. 访问

打开浏览器访问 [http://localhost:5173](http://localhost:5173)

**默认账号：**
| 用户名 | 密码 |
|--------|------|
| `admin` | `admin123` |

---

## Docker 一键部署

```bash
docker compose up -d
```

服务启动后访问 [http://localhost:3000](http://localhost:3000)

> 需要先复制并编辑 `.env` 文件（参考上方步骤 2）。

---

## 使用指南

### 添加大模型 API Key

1. 点击左侧导航「**设置**」
2. 切换到「**大模型配置**」标签
3. 点击「**添加模型**」，填写以下信息：

| 字段 | 说明 |
|------|------|
| 名称 | 自定义显示名称，如「DeepSeek 主力」 |
| 类型 | 选择对应厂商（openai / deepseek / qwen 等） |
| 模型名称 | 如 `deepseek-chat`、`gpt-4o`、`qwen-plus` |
| API Key | 对应厂商的 API Key |
| Base URL | 非标准端点时填写（大多数厂商留空） |

4. 点击「**测试连通性**」验证后保存
5. 点击「**设为默认**」将其设为对话默认模型

**各厂商获取 API Key 入口：**

| 厂商 | 控制台地址 |
|------|-----------|
| OpenAI | https://platform.openai.com/api-keys |
| Anthropic | https://console.anthropic.com/ |
| DeepSeek | https://platform.deepseek.com/ |
| 通义千问 (Qwen) | https://dashscope.console.aliyun.com/ |
| 智谱 AI | https://open.bigmodel.cn/ |
| Moonshot | https://platform.moonshot.cn/ |
| 豆包 (Doubao) | https://console.volcengine.com/ark |
| 文心一言 | https://console.bce.baidu.com/qianfan/ |
| MiniMax | https://platform.minimaxi.com/ |
| 百川 | https://platform.baichuan-ai.com/ |

---

### 创建知识库

1. 点击左侧「**知识库**」
2. 点击「**新建知识库**」，填写名称和描述
3. 进入知识库，点击「**上传文档**」

**支持的文件格式：**
- PDF (`.pdf`)
- Word (`.docx`)
- PowerPoint (`.pptx`)
- 图片 (`.jpg` / `.png`，OCR 解析)
- 纯文本 (`.txt` / `.md`)

上传后系统会自动解析并分块入库，状态变为「**就绪**」后即可检索。

---

### 与晓曼对话

1. 点击左侧「**对话**」→「**新建对话**」
2. 在输入框输入问题，按 `Enter` 发送（`Shift + Enter` 换行）

**Skill 路由规则：**

| 触发词示例 | 路由到 |
|-----------|--------|
| 怎么、如何、什么是、查一下 | RAG 知识库检索 |
| 执行、运行、run、runbook、日志分析 | MCP 工具执行 |
| 其他 | 直接调用大模型 |

---

### 注册 MCP 工具

1. 点击「**设置**」→「**MCP 工具**」
2. 填写工具名称、服务地址（支持 HTTP/SSE/WebSocket）
3. 在对话中输入触发词，晓曼会自动调用对应工具

---

## 目录结构

```
xiaoman/
├── backend/                  # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # REST API 路由
│   │   ├── models/           # SQLAlchemy ORM 模型
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层
│   │   │   ├── llm_service.py      # LiteLLM 多模型封装
│   │   │   ├── rag_service.py      # RAG 检索
│   │   │   ├── skill_router.py     # 意图路由
│   │   │   ├── document_parser.py  # 文档解析
│   │   │   └── chat_service.py     # 对话编排（SSE 流）
│   │   └── core/             # 鉴权、依赖注入
│   └── requirements.txt
│
├── frontend/                 # React 前端
│   └── src/
│       ├── pages/            # 页面组件
│       ├── components/       # 可复用组件
│       ├── store/            # Zustand 状态管理
│       ├── api/              # Axios API 客户端
│       └── hooks/            # 自定义 Hooks（含 SSE 流）
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API 文档

后端启动后访问：

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 常见问题

**Q: 启动后端报 bcrypt 相关错误？**

确保安装的是 `bcrypt==4.2.0`，而非通过 `passlib[bcrypt]` 安装的旧版：
```bash
pip install bcrypt==4.2.0
```

**Q: 前端无法连接后端？**

确认后端运行在 `8000` 端口，前端 Vite 代理已在 `vite.config.ts` 中配置 `/api` → `http://localhost:8000`。

**Q: 没有 API Key 能用吗？**

可以。未配置 API Key 时，晓曼会返回提示性 mock 响应，其余功能（知识库、MCP 工具管理等）正常使用。

**Q: 如何启用 Milvus 向量数据库？**

在 `.env` 中设置：
```env
USE_MILVUS=true
MILVUS_HOST=localhost
MILVUS_PORT=19530
```
然后通过 Docker 启动 Milvus：
```bash
docker compose up milvus -d
```

---

## 路线图

- [x] Phase 1 — Agent 核心 + 多大模型接入 + 基础对话
- [x] Phase 2 — 知识库 CRUD + 文档解析 + RAG 检索
- [ ] Phase 3 — MCP 工具完整集成 + Runbook 执行
- [ ] Phase 4 — 飞书双向集成 + Skill 体系完善

---

## License

MIT © 2024 Xiaoman
