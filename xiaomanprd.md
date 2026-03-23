# 晓曼 (Xiaoman) - 运维助理 Agent PRD

### TL;DR

晓曼（Xiaoman）是一款为DevOps/SRE工程师设计的Web端AI运维助理agent，集成RAG知识库（支持向量数据库）、MCP工具自动化（runbook执行及日志分析）、双向飞书集成、多大模型API密钥接入（支持全部主流中国模型）、及基于Skill的Agent架构。目标用户为企业中负责运维响应与自动化的团队。

---

## Goals

### Business Goals

* 运维流程runbook自动化率提升至60%+。
* 打造集中化企业级运维知识库，减少知识分散与遗失。
* 提升团队对主流国产大模型（如文心、通义等）的适配能力。

### User Goals

* 可快速查询与检索运维知识，缩短排障流程。
* 通过AI自动化执行runbook及日志分析，减少重复体力劳动。
* 实现飞书原生告警推送与交互，提升响应效率。
* 随时切换/配置最合适的大模型API密钥，即时提升Agent输出质量。

### Non-Goals

* 不支持自定义训练或微调LLM（仅调用API）。
* V1不包含移动端App（Web与飞书为唯一触达渠道）。
* 无计费、订阅等商业管理功能（v1仅关注功能构建）。

---

## User Stories

**Ops工程师（Primary）**

* 作为一名运维工程师，我希望能在故障发生时直接在Web端对晓曼提问，快速查找到相关知识或脚本方案，从而高效定位并解决问题。
* 作为一名运维工程师，我需要通过聊天对话触发MCP runbook工具，自动化执行排查与修复操作，从而减少人工介入。
* 作为一名运维工程师，我期望能在飞书收到系统告警，并直接在飞书群聊中与晓曼交互，执行runbook或获取分析结果。
* 作为一名运维工程师，我希望能上传PPT、PDF、图片等文档到知识库，让团队沉淀现有经验，方便未来检索。
* 作为一名运维工程师，我需要便捷切换不同主流大模型（OpenAI、通义千问、文心、智谱等）API Key，确保响应能力和可用性。

**Ops Team Lead（Secondary）**

* 作为运维团队负责人，我希望能在后台管理知识库版本和内容，保障内容时效性和准确性。
* 作为负责人，我希望能够统计团队自动化执行runbook和快速恢复的比率，以衡量团队整体效能提升。

---

## Functional Requirements

* **Agent Core (Priority: P0)**

  * Chat UI：现代化运维对话界面，支持文字与文件输入。
  * Skill Routing：根据用户意图自动分发至知识问答、MCP工具、知识CRUD等流程。
  * 会话管理：支持用户多轮对话与会话历史记录。
* **知识库管理 (Priority: P0)**

  * 知识库CRUD：创建、编辑、删除知识库与文档。
  * 支持多格式文档：PDF、图片（jpg/png）、docx、pptx等文件解析与上传。
  * 向量数据库集成：支持Milvus，完成知识向量化、嵌入与检索。
* **MCP工具集成 (Priority: P0)**

  * Runbook执行：支持MCP协议的自动化脚本运行。
  * 日志分析工具：能够通过MCP调用日志抓取与分析工具，自动输出诊断结论。
  * MCP协议接入：对接标准MCP通信协议，实现与现有自动化工具链兼容互通。
* **飞书集成 (Priority: P1)**

  * 接收消息与告警：飞书Bot可在群聊或私聊中收到用户/系统消息与告警。
  * 推送通知与诊断报告：告警汇总等推送至指定飞书群组。
* **LLM Provider管理 (Priority: P0)**

  * 多大模型API密钥配置：兼容OpenAI、Anthropic、Qwen（千问）、Wenxin（文心）、Doubao、Zhipu（智谱）、Moonshot、DeepSeek、MiniMax、Baichuan等主流API，支持随时新增/切换/禁用密钥。
* **Skill框架 (Priority: P1)**

  * Skill定义、管理与调用：支持新增、组合和按需激活各种Agent技能（如运维问答、自动脚本等）。

---

## User Experience

**Entry Point & First-Time User Experience**

* 上线首次自动推送简明产品简介和功能引导（弹窗或欢迎tab），包含知识库上传、MCP工具调用、飞书绑定说明等。
* 管理员可进入后台界面，对知识库、API Key等进行初始化配置。

**Core Experience**

* **Step 1:** 用户登录后进入对话主界面，“与晓曼对话”。

  * 支持输入文字问题、粘贴飞书告警截图、上传脚本、日志等。
  * 出错校验：如文件不支持，弹窗友好提示。
  * 成功后进入下一步或显示工具栏（如知识库检索/MCP工具入口）。
* **Step 2:** 用户提问（如“数据库慢怎么办？”）或点击工具按钮，晓曼根据意图分流：

  * 知识检索（RAG），高亮展示相关runbook或经验文档。
  * MCP工具调用：如日志分析/自动脚本，Agent提示“已执行工具：日志分析”，展示实时进度与结果摘要。
  * 可以追加提问或进一步操作，如“请继续执行方案二”。
* **Step 3:** 对接飞书体验：

  * 告警发生时飞书Bot自动推送消息，用户可直接在飞书对话内控制晓曼（如“帮我分析日志”）。
  * 分析/执行结果自动推送回飞书群/个人，标明结论或后续建议。
* **Step 4:** 知识库管理：

  * 管理员进入后台，上传/编辑/删除知识文档，支持批量或拖拽上传，自动触发向量化入库/分词。
  * 支持查看知识向量检索命中率与文档热度。
* **Step 5:** LLM API Key切换

  * 管理员可在设置中心添加/切换/禁用不同厂商API Key；
  * 当前channel所用大模型及状态提示，UI支持热切换与测试连通性。

**Advanced Features & Edge Cases**

* MCP工具调用超时或失败，Chat UI需清晰反馈、允许重试，并建议常见排障思路。
* 文档上传如遇格式不支持，给出明确的格式指引和上传建议。
* LLM API Key异常（额度、权限问题），界面红色直观提示、后台日志报警。
* 支持多轮复杂会话和意图纠错/校正。

**UI/UX Highlights**

* 响应式布局，兼容主流浏览器，支持PC、Pad端浏览。
* 高对比度配色，适配夜间模式。
* 文件上传操作可取消、进度可视化。
* 错误提示明确、引导性强，例如API Key缺失弹窗、Knowledge Base检索无数据时的建议。
* 可在UI一键导入飞书Bot/授权操作。
* 支持无障碍快捷键与屏幕阅读友好。

---

## Narrative

午夜2点，Grace作为公司的SRE值班工程师，突然在飞书收到一条数据库延迟飙升的告警。困意尚未消散，她直接在飞书群聊输入“@晓曼，帮我分析下数据库慢的原因”。晓曼立即响应：首先利用内嵌RAG知识库，检索出专属的数据库排障runbook文档，并归纳重点指引。随后，晓曼自动通过MCP工具接口远程启动日志分析流程，将诊断摘要汇总并推送回飞书群内。整个闭环无需Grace登陆VPN、切换工具、查阅多平台资料，数分钟内就获得了诊断和下一步处置建议。晓曼的加入，不仅让Ops团队夜间响应更加高效，也显著减轻了值班工程师的心理压力，企业的平均恢复时间也因此大幅下降。

---

## Success Metrics

### User-Centric Metrics

* 日活跃运维工程师数（DAU），以Web/飞书独立用户统计。
* 知识库检索成功率，用户查询后获得有效答案占比。
* MCP工具调用成功率，自动化脚本实际执行无误的比率。

### Business Metrics

* MTTR环比下降幅度（目标30%），从系统监控和工单恢复时长中收集。
* Runbook自动化执行比例，自动化处理的告警/工单数量占比。

### Technical Metrics

* RAG知识检索平均延迟 <2s。
* MCP工具远程调用执行成功率 >95%。
* 系统整体服务可用性 >99.5%。

### Tracking Plan

* Chat session创建和互动数。
* MCP工具调用次数与状态。
* 知识库内容查询和文档上传事件。
* 飞书消息通知/响应事件。
* LLM API key切换与失败事件。

---

## Technical Considerations

### Technical Needs

* 向量数据库（如Milvus/Qdrant）实现RAG知识检索。
* 文档抽取与向量化管道，支持PDF/image/docx/pptx自动切分+解析+embedding。
* MCP协议客户端，支持自动化工具和脚本远程安全调用。
* 飞书Open API集成（Bot webhook与事件订阅）。
* LLM抽象层，可兼容10+主流大模型厂商API Key，灵活切换。
* 会话与知识管理前后端，安全隔离。

### Integration Points

* 企业现有运维自动化工具链（MCP工具/脚本服务）。
* 向量数据库云服务或本地部署实例。
* 飞书Bot与企业消息通知系统。
* 主流中国与国际LLM API服务。

### Data Storage & Privacy

* 支持大文档自动chunk并embedding存储，向量库按库/业务隔离。
* 用户对话与操作日志记录，审计与运营追溯。
* API Key加密存储，后台权限严格管控。
* 符合企业数据合规策略，不做敏感内容外传。

### Scalability & Performance

* MCP工具调用采用异步队列方案，应对高并发及长耗时任务。
* RAG检索和embedding任务分布式处理，提升吞吐。
* 支持最大1000人团队日活不降速。

### Potential Challenges

* 飞书Bot权限申请、安全隔离策略核查。
* 多主流大模型API变更或额度受限需适时切换。
* 文档识别与信息解析的兼容性，如图片OCR准确率。

---

## Milestones & Sequencing

### Project Estimate

* **Medium:** 3–5周，适合快速敏捷开发的初创团队。

### Team Size & Composition

* **Medium Team:** 3–4人。

  * 1×全栈工程师（前后端+API集成）
  * 1×产品or运维工程师（流程设计+MCP集成）
  * 1×UI/UX设计师（简洁高效的运维体验）
  * 可选1×AI工程师（RAG&模型API支持/适配）

### Suggested Phases

**Phase 1: Agent核心模块&大模型接入+基础Web对话（1–2周）**

* Key Deliverables: 基础聊天UI、LLM多API管理、核心Skill路由（工程/AI）
* Dependencies: 产品流程确定，API Key申请

**Phase 2: 知识库CRUD+向量检索管道+多格式文档解析（2–3周）**

* Key Deliverables: 后台CRUD、文档上传与分片、向量库对接（工程/设计）
* Dependencies: 向量数据库部署，OCR/Parser工具选型

**Phase 3: MCP工具集成+自动化runbook执行与日志分析（3–4周）**

* Key Deliverables: MCP协议客户端、UI触发器、脚本/日志分析功能（工程/运维产品）
* Dependencies: 企业现有MCP工具/测试环境

**Phase 4: 飞书双向集成+Skill体系完善+体验打磨（4–5周）**

* Key Deliverables: 飞书Bot webhook&推送、Skill管理、边界场景&UI优化（全体）
* Dependencies: 飞书Bot审批完成，整体联调

---
