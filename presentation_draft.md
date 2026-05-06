# 运维助手 Agent 系统 · 团队介绍文档

---

## 一、背景与痛点

随着基础设施规模扩大，传统的运维工作正面临三个典型困境：

### 痛点一：信息分散，上下文切换成本高

运当线上问题发生时，需要手动将多个平台的信息汇总，再结合历史文档定位问题，平均每次故障响应的"信息收集阶段"就耗费大量时间。晓曼系统将知识库（RAG）、工具调用（MCP 工具）和外部搜索三种信息来源统一聚合在一个对话框中，工程师无需切换上下文。

### 痛点二：重复性操作多，执行依赖人工干预

大量运维操作属于"已知场景的标准动作"——例如创建故障通知群。这类工作虽然可以脚本化，但调用入口分散、参数传入繁琐，难以形成统一的自然语言交互界面。晓曼通过 MCP 工具协议将这些脚本和 API 封装为 LLM 可调用的"工具"，工程师用自然语言描述意图，由 Agent 自动选择并执行对应工具。

### 痛点三：团队协同链路长，事件通知流转慢

当故障发生时，往往需要手动创建飞书群、@相关人员、发送告警摘要——这些步骤在凌晨告警时极易出错或遗漏。晓曼集成了飞书 IM，Agent 可以直接调用内置工具创建协作群、发送告警消息，将"发现问题 → 拉群 → 通知"的链路自动化压缩到秒级。

---

## 二、系统一句话介绍

**晓曼（Xiaoman）是一款面向 DevOps/SRE 工程师的 AI 运维助手平台，通过自然语言对话驱动工具调用、知识检索与协同通知，让工程师用"说话"代替"操作"。**

进一步展开：

- 系统基于大语言模型（支持 OpenAI、Claude、DeepSeek、Qwen 等 10+ 主流模型），通过 Agent 循环（ReAct 范式）在自然语言对话中自主决策、调用工具、检索知识。
- 工具侧采用 MCP（Model Context Protocol）标准协议，任何符合 MCP 规范的运维脚本或 API 均可被无缝接入，无需修改 Agent 核心代码。
- 知识侧支持上传 PDF、Word、PPT、Markdown 等多种格式文档，通过向量检索（RAG）将历史 Runbook、故障复盘报告注入对话上下文，让 AI 具备"企业私有知识"。

---

## 三、系统工作原理与架构设计

### 3.1 整体架构分层

系统从外到内共分为四层，各层职责边界清晰：

```
┌─────────────────────────────────────────────────────────┐
│                     接入层 (Access Layer)                 │
│  ┌─────────────────┐         ┌──────────────────────┐   │
│  │  Web 前端 (React) │         │  飞书 Webhook/IM 接入  │   │
│  └────────┬────────┘         └──────────┬───────────┘   │
└───────────┼──────────────────────────────┼───────────────┘
            │ HTTP (REST + SSE)            │ HTTP Webhook
┌───────────▼──────────────────────────────▼───────────────┐
│                   规划与编排层 (Orchestration Layer)        │
│              FastAPI 路由 → Chat Service Agent Loop        │
│          [意图理解] → [上下文组装] → [工具决策] → [回复生成]  │
└──────────────────────────────┬────────────────────────────┘
                               │ 异步调用
┌──────────────────────────────▼────────────────────────────┐
│                   能力执行层 (Execution Layer)               │
│   ┌─────────────┐  ┌──────────┐  ┌──────┐  ┌──────────┐  │
│   │  LLM Service │  │RAG Service│  │ MCP  │  │  Feishu  │  │
│   │ (LiteLLM封装) │  │(ChromaDB) │  │Service│  │ Service  │  │
│   └─────────────┘  └──────────┘  └──────┘  └──────────┘  │
└──────────────────────────────┬────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────┐
│                    基础设施层 (Infrastructure Layer)         │
│   SQLite/PostgreSQL (关系数据)  +  ChromaDB (向量数据)      │
│   .env 加密存储（API Key）       +  文件系统（文档上传）      │
└───────────────────────────────────────────────────────────┘
```

| 层级         | 职责边界                                                                  |
| ------------ | ------------------------------------------------------------------------- |
| 接入层       | 接收用户输入（Web UI 或飞书消息），建立 SSE 长连接，将请求路由到后端      |
| 规划与编排层 | 核心 Agent 循环所在层，负责任务分解、工具选择、消息历史管理、流式输出编排 |
| 能力执行层   | 将规划层的指令落地：调用 LLM、检索向量知识库、执行 MCP 工具、推送飞书消息 |
| 基础设施层   | 持久化存储（会话、消息、配置、向量索引），不包含任何业务逻辑              |

---

### 3.2 核心模块与职责划分

#### 后端核心服务（`backend/app/services/`）

| 模块                   | 文件                      | 职责                                                                        |
| ---------------------- | ------------------------- | --------------------------------------------------------------------------- |
| **Agent 编排器** | `chat_service.py`       | 整个系统的核心，实现 Agent 循环、工具调度、流式输出（301 行）               |
| **LLM 网关**     | `llm_service.py`        | 通过 LiteLLM 统一封装 10+ 大模型，处理流式 token 和工具调用拆包（204 行）   |
| **RAG 服务**     | `rag_service.py`        | 文档分块向量化入库、相似性检索、知识上下文注入（266 行）                    |
| **MCP 服务**     | `mcp_service.py`        | 实现 MCP 协议客户端，支持 SSE/HTTP 两种 transport，工具发现与执行（227 行） |
| **飞书服务**     | `feishu_service.py`     | 飞书事件验签解密、消息收发、群组管理、Token 缓存（350+ 行）                 |
| **文档解析器**   | `document_parser.py`    | 解析 PDF/DOCX/PPTX/MD/TXT/图片，调用 OCR，文本分块预处理                    |
| **向量嵌入服务** | `embed_service.py`      | 嵌入模型调用的抽象层，支持多个 Embed 提供商                                 |
| **OCR 服务**     | `ocr_service.py`        | 图片文字识别，支持 Tesseract 和 LLM 视觉模型双后端                          |
| **网络搜索服务** | `web_search_service.py` | 集成 Tavily / DuckDuckGo，外部实时信息检索                                  |
| **加密服务**     | `encryption.py`         | Fernet 对称加密，保护 API Key 等敏感字段                                    |

#### 后端 API 路由（`backend/app/api/v1/`）

11 个路由模块，遵循 REST 风格，通过 FastAPI 依赖注入获取当前用户和数据库会话。所有敏感接口要求 Bearer Token 认证。

#### 前端核心（`frontend/src/`）

| 模块                          | 职责                                                                   |
| ----------------------------- | ---------------------------------------------------------------------- |
| `hooks/useStreamingChat.ts` | SSE 流解析钩子，按事件类型分发 token/citation/tool_call 到全局状态     |
| `store/chatStore.ts`        | Zustand 状态管理，维护消息列表的增量更新（appendToken/appendThinking） |
| `components/chat/`          | 对话界面：ChatWindow、MessageBubble、ToolCallCard、SourceCitation      |
| `components/knowledge/`     | 知识库管理：文档上传、分块配置                                         |
| `components/llm/`           | LLM 提供商配置：模型选择、连通性测试                                   |

#### 模块依赖关系

```
Chat API Route
    └── ChatService (Agent Loop)
            ├── LLMService ← llm_providers (DB)
            ├── RAGService ← ChromaDB + EmbedService
            ├── MCPService ← MCP Tools (DB) → 外部 MCP Server
            ├── WebSearchService → Tavily/DuckDuckGo
            └── FeishuService ← feishu_configs (DB) → 飞书 API
```

---

### 3.3 核心组件交互关系

#### 规划器（Planner）：Agent 循环中的决策机制

系统采用 **ReAct（Reasoning + Acting）** 范式。LLM 在每轮对话中扮演规划器角色：

1. LLM 接收完整上下文（系统提示 + 历史对话 + RAG 结果 + 可用工具定义）
2. LLM 输出两种结果之一：
   - **纯文本回答** → 本轮任务完成，退出循环
   - **工具调用指令**（`finish_reason = "tool_calls"`）→ 继续循环，执行工具后将结果追加到消息历史，再次请求 LLM
3. 安全限制：最多循环 **20 次**（`MAX_TOOL_ITERATIONS = 20`），防止无限循环

LLM 并不显式分解任务为"子任务列表"，而是通过多轮工具调用隐式实现任务分解——这是一种轻量级的 ReAct 实现方式。

#### 记忆系统（Memory）

| 维度                             | 实现方式                                                                               |
| -------------------------------- | -------------------------------------------------------------------------------------- |
| **短期记忆（会话上下文）** | 每轮调用 LLM 前，从数据库加载当前 session 的所有历史消息，全量追加到 `messages` 数组 |
| **工具调用记忆**           | 每次工具执行后，以 `role: "tool"` 消息追加结果，LLM 下一轮可"看到"工具输出           |
| **知识库记忆（长期知识）** | 用户上传的文档通过 ChromaDB 向量化存储，每次对话通过相似性检索动态注入系统提示         |
| **会话持久化**             | 对话历史持久化到 SQLite/PostgreSQL，关闭浏览器后不丢失                                 |

当前系统**不实现滑动窗口**：历史消息全量送给 LLM，当对话极长时存在超出 token 上限的风险（已知限制）。

#### 工具调用（Tool Use）机制

```
① 注册阶段（管理员操作）
   管理员在 UI 填写 MCP Server URL
   → 系统自动调用 tools/list 发现工具列表
   → 将工具名、描述、参数 JSON Schema 存入数据库

② 注入阶段（每次对话）
   Chat Service 从数据库加载所有 is_active=True 的工具
   → 转换为 OpenAI function calling 格式
   → 随 messages 一起传给 LLM

③ 路由阶段（LLM 决策）
   LLM 根据工具描述自主选择调用哪个工具、传入哪些参数
   → 返回 tool_calls 结构体（含工具名 + 参数 JSON）

④ 执行阶段（MCP Service）
   SSE Transport: 与 MCP Server 建立长连接，发送 tools/call 请求
   HTTP Transport: 发送 JSON-RPC 2.0 请求到 MCP Server 端点
   → 流式返回执行状态事件

⑤ 回收阶段
   执行结果以 role:"tool" 消息追加到 messages
   → 下一轮 LLM 调用时可见，LLM 据此生成最终回答
```

飞书内置工具（`feishu_create_group`）无需外部 MCP Server，直接在 Chat Service 内执行，是"内置工具"与"外部工具"的混合路由模式。

#### 执行循环（Agent Loop）详解

```python
# 简化伪代码，实际位于 chat_service.py:182-264
iteration = 0
MAX_TOOL_ITERATIONS = 20

while iteration < MAX_TOOL_ITERATIONS:
    iteration += 1

    # 请求 LLM（流式）
    async for delta in llm_service.stream_chat(messages, provider, tools=llm_tools):
        if delta 是工具调用:
            收集工具调用指令
        elif delta 是推理内容(thinking):
            yield SSE event: thinking
        else:
            yield SSE event: token  # 实时推送文字给前端

    if 本轮没有工具调用:
        break  # ← 退出条件一：LLM 给出纯文本答案

    # 执行工具
    for 每个工具调用:
        yield SSE event: tool_call (status: running)
        执行 MCP 工具，获取结果
        yield SSE event: tool_call (status: done/error)
        messages.append({role:"tool", content:工具结果})

# 兜底：如果工具执行了但没有生成文字，强制 LLM 汇总
if 有工具调用 but 无文字输出:
    再次请求 LLM 进行总结（无工具），yield tokens

# 持久化 + 结束
保存 assistant 消息到数据库
yield SSE event: done
```

**循环退出条件（任一满足即退出）：**

1. LLM 本轮返回纯文本（无工具调用）
2. 达到 `MAX_TOOL_ITERATIONS = 20` 次上限
3. 工具执行报错（当前实现：错误信息追加到上下文，LLM 决定是否继续）

---

### 3.4 数据流与控制流

追踪一条完整请求的生命周期（示例：用户问"帮我查一下今天的部署日志，然后在飞书拉个群通知相关人员"）：

**① 用户输入接收与预处理**

```
前端 useStreamingChat.ts
  → POST /api/v1/chat/stream
    Body: { session_id, content, kb_ids: [...], web_search: false }
  → FastAPI 路由验证 Bearer Token（JWT 解码 → 查数据库确认用户存在且激活）
  → 将用户消息持久化到 chat_messages 表（role: "user"）
  → 返回 text/event-stream 响应头，建立 SSE 长连接
```

**② 意图理解与上下文组装**

Chat Service 在调用 LLM 前，组装完整上下文：

```
系统提示（system prompt）= 
    固定角色描述
  + 【如果有 kb_ids】RAG 检索结果（top-k 相关文档片段 + 引用来源）
  + 【如果启用 web_search】网络搜索摘要

消息历史（messages）=
    所有历史 user/assistant/tool 消息（从 DB 加载）
  + 当前用户输入

可用工具列表（tools）=
    数据库中所有 is_active=True 的 MCP 工具（OpenAI function schema 格式）
  + 飞书内置工具（feishu_create_group）
```

**③ 决策生成**

LLM 接收上述完整上下文后：

- 分析用户意图 → 识别需要两步操作："查日志" + "建群"
- 第一轮输出工具调用：`{"name": "query_deploy_logs", "arguments": {"date": "today"}}`
- 执行日志查询工具，将结果追加到 messages
- 第二轮 LLM 收到日志结果，继续输出工具调用：`{"name": "feishu_create_group", "arguments": {...}}`
- 执行建群，追加结果
- 第三轮 LLM 收到建群结果，输出最终总结文字，退出循环

**④ 工具调用与结果回收**

以 MCP 工具（SSE transport）为例：

```
MCPService.execute_tool_stream(tool, args)
  → 建立 SSE 连接到 MCP Server
  → 发送 tools/call 请求（JSON-RPC 2.0）
  → 流式接收执行事件（running / success / error）
  → 每个事件 yield 给 Chat Service
  → Chat Service 将事件实时 yield 为 SSE 给前端（event: tool_call）
  → 工具执行完毕，完整输出以 role:"tool" 追加到 messages
```

飞书建群工具（内置）：直接调用飞书 REST API → 创建群组 → 返回群 ID 和邀请链接。

**⑤ 结果组装与返回**

```
Agent Loop 结束
  → 将 assistant 完整回答保存到 chat_messages 表（含 meta 字段记录执行元数据）
  → yield "event: done\ndata: {message_id}\n\n"
  → SSE 连接关闭

前端 useStreamingChat.ts 接收到 done 事件
  → finalizeMessage(sessionId, messageId)
  → chatStore 中 streamingMessageId 清空
  → 消息气泡从"流式输入"状态转为"已完成"状态
```

---

### 3.5 关键算法与设计模式

#### 1. 流式工具调用重组（Streaming Tool Call Reassembly）

LLM 的流式输出中，工具调用指令是**分片传输**的（函数名、参数 JSON 分多个 chunk 到达）。`llm_service.py` 通过索引累加器重组：

```python
tool_call_acc: Dict[int, Dict[str, Any]] = {}
# 按 tc.index 累加 name 和 arguments 字符串片段
# 直到 finish_reason == "tool_calls" 时，一次性 JSON.parse 完整参数
```

这一设计解决了"流式 API 返回 + 工具调用解析"的核心矛盾，是系统低延迟的关键之一。

#### 2. SSE 多类型事件协议

系统自定义了一套 SSE 事件协议，将不同类型的信息分开传输，前端按事件类型分发到不同 UI 组件：

| 事件类型       | 携带数据                 | 前端处理                         |
| -------------- | ------------------------ | -------------------------------- |
| `token`      | 文字 delta               | 追加到消息气泡                   |
| `thinking`   | 推理过程 delta           | 追加到折叠面板（DeepSeek-R1 等） |
| `citation`   | 知识库引用 + 相似度分数  | 显示来源卡片                     |
| `tool_call`  | 工具名 + 执行状态 + 输出 | 工具调用进度卡片                 |
| `web_result` | 搜索结果摘要             | 网络搜索结果卡片                 |
| `error`      | 错误信息                 | 错误提示                         |
| `done`       | message_id               | 消息最终化                       |

#### 3. 多模型统一接入（LiteLLM Abstraction）

通过 LiteLLM 库将 10+ 模型统一为相同的 `acompletion()` 接口，`provider_type` 字段决定路由：

- `openai` → `gpt-4o` 等
- `anthropic` → `claude-opus-4-6` 等
- `deepseek` → `deepseek-chat` 等（路由到 `api.deepseek.com`）
- `custom` → 用户自定义 base_url（适配私有化部署的模型）

这一设计使得新增模型支持无需修改 Agent 核心逻辑，仅需在数据库中添加 Provider 配置。

#### 4. RAG 三段式注入（检索 → 重排 → 注入）

```
① 向量检索：ChromaDB HNSW 索引，余弦相似度 top-k
② 结果格式化：distance 转换为 similarity score（1 - distance）
③ 上下文注入：以 XML-like 块格式追加到 system prompt 末尾
   → LLM 引用时，系统提取 chunk_id 作为 citation 事件发送给前端
```

#### 5. API Key 加密存储（Fernet Symmetric Encryption）

数据库中所有第三方 API Key（LLM、Embed、OCR 提供商）均以 Fernet 对称加密存储，密钥从 `.env` 读取（首次运行自动生成）。运行时解密，内存中明文不持久化，避免数据库泄露导致密钥暴露。

---

## 四、核心能力演示场景

### 场景一：故障快速溯源

**触发输入示例：**

> "我们的支付服务从下午 2 点开始报错，帮我查一下最近的错误日志，总结一下根因"

**系统处理过程：**

1. Chat Service 加载当前会话历史 + 系统提示
2. 从向量知识库检索"支付服务错误处理"相关文档（若有 Runbook）→ 注入上下文
3. LLM 分析意图，决定调用 MCP 工具 `query_error_logs`（参数：`service=payment, since=14:00`）
4. MCP Service 向日志查询服务发送请求，流式返回日志条目
5. LLM 收到日志，生成结构化根因分析报告
6. 前端实时展示：工具调用进度 + 逐字生成的分析文字 + 知识库引用来源

**输出结果示例：**

```
根据日志分析，支付服务在 14:02 开始出现以下错误：
- 数据库连接超时（占错误总量 87%）
- 连接池耗尽（peak: 100/100 connections）

根因推断：数据库主机 db-primary-01 在 13:58 触发了慢查询，
导致连接长期占用，进而耗尽连接池。

建议立即执行 [Runbook: 数据库慢查询处理流程]（引用来源: kb_001）
```

---

### 场景二：自动化故障通知

**触发输入示例：**

> "刚才的支付故障需要拉个群，把张三、李四、王五加进来，告诉他们情况"

**系统处理过程：**

1. LLM 识别需要调用飞书内置工具 `feishu_create_group`
2. Chat Service 直接调用 FeishuService（无需外部 MCP Server）
3. 飞书 API：获取 tenant access token → 创建群组 → 邀请成员
4. LLM 收到群组创建结果（群 ID + 链接），自动在群内发送故障摘要

**输出结果示例：**

```
已为您创建飞书群组「支付服务故障处理-0402」
群成员：张三、李四、王五
已发送初始告警摘要至群内。

群链接：https://applink.feishu.cn/...
```

---

### 场景三：知识库辅助决策

**触发输入示例：**

> "我们要做 Redis 主从切换，有没有什么需要注意的地方？"

**系统处理过程：**

1. 用户在对话中选择了"运维手册"知识库
2. RAG Service 向量检索"Redis 主从切换"相关 Runbook → 找到 top-3 相关片段
3. 片段作为上下文注入系统提示，附带相似度分数（0.87, 0.82, 0.76）
4. LLM 基于私有 Runbook 生成定制化建议，引用具体文档章节

**输出结果示例：**

```
根据公司 Redis 运维手册，主从切换需注意以下事项：

1. **切换前检查**：确认从节点 replication_offset 与主节点差值 < 1000（手册第 3.2 节）
2. **切换命令**：执行 `REPLICAOF NO ONE` 前需先暂停业务写入
3. **监控指标**：切换后观察 `redis_connected_clients` 指标 5 分钟

来源：[Redis 高可用运维手册 v2.3]（相似度 87%）
```

---

## 五、技术实现概览

### 5.1 主要技术栈

| 层次                  | 技术选型                                                                                      | 版本/说明                                |
| --------------------- | --------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **AI 模型接入** | LiteLLM                                                                                       | 统一封装 10+ 大模型，支持流式 + 工具调用 |
| **LLM 支持**    | OpenAI、Anthropic Claude、DeepSeek、Qwen（通义千问）、智谱 GLM、Moonshot、豆包、MiniMax、百川 | 含国内外主流模型                         |
| **工具协议**    | MCP（Model Context Protocol）                                                                 | SSE + HTTP 双 transport                  |
| **后端框架**    | FastAPI                                                                                       | 异步优先（Python 3.11+）                 |
| **ORM**         | SQLAlchemy 2.0（Async）                                                                       | aiosqlite / asyncpg                      |
| **向量数据库**  | ChromaDB                                                                                      | 持久化本地 HNSW 索引                     |
| **前端框架**    | React 18 + TypeScript                                                                         | Vite 构建                                |
| **状态管理**    | Zustand                                                                                       | 轻量，支持增量消息更新                   |
| **UI 样式**     | Tailwind CSS                                                                                  |                                          |
| **认证**        | JWT（HS256）+ bcrypt                                                                          | 7 天有效期                               |
| **加密**        | Fernet（cryptography 库）                                                                     | API Key 静态加密                         |
| **部署**        | Docker Compose                                                                                | 支持 PostgreSQL 生产模式                 |

### 5.2 项目结构概览

```
xiaoman/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST API 路由层（11 个模块，约 800 行）
│   │   │   ├── auth.py          # 登录/注册/用户信息
│   │   │   ├── chat.py          # 会话管理 + SSE 流式聊天（核心入口）
│   │   │   ├── knowledge.py     # 知识库 CRUD + 文档上传 + 向量搜索
│   │   │   ├── mcp_tools.py     # MCP 工具注册、发现、执行
│   │   │   ├── llm_providers.py # LLM 提供商配置 + 连通测试
│   │   │   ├── embed_providers.py # 嵌入模型提供商配置
│   │   │   ├── ocr_providers.py # OCR 提供商配置
│   │   │   ├── feishu.py        # 飞书 Webhook 接收 + 配置
│   │   │   ├── system.py        # 系统设置
│   │   │   └── dc_inspection.py # 数据中心巡检功能
│   │   ├── models/              # SQLAlchemy ORM 模型（10 个实体）
│   │   ├── schemas/             # Pydantic 请求/响应 schema
│   │   ├── services/            # 核心业务逻辑（约 1,600 行）
│   │   │   ├── chat_service.py  # ★ Agent 循环核心（301 行）
│   │   │   ├── llm_service.py   # ★ LLM 网关（204 行）
│   │   │   ├── rag_service.py   # ★ 向量检索（266 行）
│   │   │   ├── mcp_service.py   # ★ MCP 协议客户端（227 行）
│   │   │   ├── feishu_service.py# ★ 飞书集成（350+ 行）
│   │   │   └── ...（文档解析、加密、OCR、搜索等）
│   │   ├── core/                # 横切关注点（JWT、依赖注入、异常处理）
│   │   ├── config.py            # 环境变量配置（Pydantic Settings）
│   │   ├── database.py          # 数据库初始化 + 表创建
│   │   └── main.py              # FastAPI 应用入口 + lifespan 钩子
│   ├── requirements.txt         # 26 个依赖
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                 # Axios API 客户端（按功能拆分）
│   │   ├── components/          # React 组件（chat/knowledge/llm/layout）
│   │   ├── hooks/               # 自定义 Hook（SSE 流解析、认证）
│   │   ├── store/               # Zustand 状态 store
│   │   └── types/               # TypeScript 接口定义
│   └── package.json
├── docker-compose.yml           # 一键启动（backend + frontend）
├── .env.example                 # 环境变量模板
└── README.md                    # 部署与使用文档
```

### 5.3 关键技术难题及解决方案

**难题一：流式响应 + 工具调用的兼容性**

大模型返回工具调用时，参数 JSON 以多个 chunk 分片传输。直接解析任意 chunk 会导致 JSON 不完整报错。系统通过**按 index 索引累加器**方案，等待 `finish_reason == "tool_calls"` 触发后再一次性解析，完美解决流式分片问题。

**难题二：国内外多模型兼容**

DeepSeek、Qwen、智谱等国内模型与 OpenAI API 存在细微差异（base_url、模型前缀、thinking content 字段名）。通过 LiteLLM 统一封装后，系统只需维护 `provider_type` → `base_url` 的映射表，模型切换对 Agent 层完全透明。

**难题三：飞书事件安全验证**

飞书 Webhook 需要验证事件签名（SHA256）并解密事件体（AES-256-CBC + PKCS7），同时处理 URL 验证挑战（challenge-response）。飞书服务模块完整实现了这一安全链路，确保只有合法的飞书平台事件才能触发 Agent。

**难题四：前端实时流体验**

SSE 流需要在前端以极低延迟更新 UI，同时处理多种事件类型（文字/工具状态/引用/思维链）。通过 Zustand 的 `appendToken` 增量更新（而非整体替换消息对象），避免了大量 DOM 重渲染，保证了流畅的打字机效果。

---

## 六、当前局限与后续计划

### 6.1 已知限制

**限制一：无上下文窗口管理**

当前实现将会话内所有历史消息全量传给 LLM，对于长对话（100+ 轮）存在超出模型 token 限制的风险。目前依赖用户手动开启新会话来绕过此问题。

**限制二：工具串行执行**

当 LLM 在一轮中指定多个工具调用时，系统按顺序逐个执行，无并发调度。对于需要同时查询多个系统的场景（如同时查日志 + 查监控），存在额外延迟。
