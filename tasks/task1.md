# 任务：实现企业级 AI Agent 的权限控制系统

请帮我设计并实现一个企业共享 AI Agent 的权限控制模块。要求**简洁实用**，不要过度设计。先进入 plan 模式，输出文件树、模块接口、数据库 schema 和关键流程图给我确认，再开始写代码。

## 设计原则

1. 最少概念覆盖最多场景，避免 ABAC 那种属性堆砌
2. 权限在 Agent 入口统一过滤，不在每个 skill 内部判断
3. Prompt 层面不做权限约束，必须在代码路径上硬拦截
4. 所有策略由管理员在网页配置，无配置文件
5. 审计日志优先级高于权限粒度

## 三层模型

### 第一层：身份（Who）

管理员新建，只用两个字段：

- `role`: `employee` | `manager` | `admin`
- `dept`: `finance` | `sales` | `rd` | `hr` | ...（部门列表也由管理员维护）

定义 `User` 数据类，包含 `user_id`、`role`、`dept` 字段。

### 第二层：资源分级（What）

所有 skills、tools、知识库统一打三级标签：

| level          | 含义                           | 示例                 |
| -------------- | ------------------------------ | -------------------- |
| `public`     | 全员可用                       | 通用问答、日程查询   |
| `internal`   | 按部门可见                     | 财务报表、CRM 工具   |
| `restricted` | 按角色+部门，且写操作/敏感操作 | 薪资数据、删除类操作 |

### 第三层：策略存储（How）

**数据库 + 内存缓存**，全部由管理员在网页配置，系统初始化时数据库为空，管理员通过界面录入。

#### 数据库表结构

使用 SQLite（开发）/ PostgreSQL（生产）：

```sql
-- 部门字典
CREATE TABLE departments (
  code TEXT PRIMARY KEY,           -- finance/sales/rd/hr
  name TEXT NOT NULL,              -- 显示名
  enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP
);

-- 资源策略表
CREATE TABLE resource_policies (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,       -- 资源唯一标识，如 salary_query
  display_name TEXT NOT NULL,      -- 给管理员看的名字
  description TEXT,
  type TEXT NOT NULL,              -- tool/skill/knowledge_base
  level TEXT NOT NULL,             -- public/internal/restricted
  allow_dept TEXT,                 -- JSON 数组，如 ["hr","finance"]
  allow_role TEXT,                 -- JSON 数组，如 ["manager","admin"]
  write BOOLEAN DEFAULT FALSE,
  require_confirm BOOLEAN DEFAULT FALSE,
  enabled BOOLEAN DEFAULT TRUE,
  updated_at TIMESTAMP,
  updated_by TEXT
);

-- 变更历史表（审计用）
CREATE TABLE policy_changes (
  id INTEGER PRIMARY KEY,
  policy_name TEXT NOT NULL,
  action TEXT NOT NULL,            -- create/update/delete/enable/disable
  before_value TEXT,               -- JSON 快照
  after_value TEXT,                -- JSON 快照
  changed_by TEXT NOT NULL,
  changed_at TIMESTAMP NOT NULL,
  reason TEXT NOT NULL             -- 必填
);

-- 配置版本号（用于多实例缓存失效）
CREATE TABLE policy_version (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  version INTEGER NOT NULL,
  updated_at TIMESTAMP
);
```

## 需要实现的模块

### 1. `policy.py` — 策略判定与管理

#### 运行时判定

- `load_policies()`：从 DB 读取启用的策略，写入内存缓存，记录当前 version
- `can_access(user, resource_name) -> bool`：
  - 资源不存在或 `enabled=false`：拒绝
  - `public`：放行
  - `internal`：检查 `allow_dept`
  - `restricted`：同时检查 `allow_dept` 和 `allow_role`
- `requires_confirmation(resource_name) -> bool`
- 缓存失效：每次判定前对比当前 `policy_version.version`，不一致则重载

#### 管理 API

```python
def list_policies(filters=None) -> list
def get_policy(name) -> Policy
def create_policy(policy_data, operator, reason) -> Policy
def update_policy(name, changes, operator, reason) -> Policy
def delete_policy(name, operator, reason) -> bool   # 软删除
def toggle_policy(name, enabled, operator, reason) -> Policy
def get_change_history(name=None, limit=50) -> list
```

**所有写操作必须**：

- `@require_admin` 校验调用者
- 写入 `policy_changes` 记录前后值和 `reason`（必填）
- 递增 `policy_version.version` 触发缓存失效

### 2. `gatekeeper.py` — Agent 入口过滤器

- `filter_capabilities(user, all_tools, all_skills, all_kbs)` 返回该用户可见的能力清单
- **关键**：把过滤后的清单交给 LLM 规划，让 LLM 完全感知不到无权限的能力
- 提供装饰器 `@require_permission(resource_name)` 给工具调用兜底拦截

### 3. `kb_filter.py` — 知识库元数据过滤

- 不要建多个独立库，**单库 + metadata 标签**
- 文档元数据包含 `dept` 和 `level`
- 向量召回后做一次 metadata 过滤再返回：
  `filter_chunks(user, retrieved_chunks) -> filtered_chunks`

### 4. `audit.py` — 审计日志

- 记录字段：`timestamp`、`user_id`、`resource_name`、`action`（read/write）、`params`、`result_summary`、`allowed`（bool）、`reason_if_denied`
- 所有工具调用**强制**经过 audit 包装，包括被拒绝的请求
- 输出到 JSONL 文件，方便后续接 ELK/Loki

### 5. `confirm.py` — 敏感操作二次确认

- 对 `require_confirm=true` 的工具，返回一个待确认的 token，等待人工点击确认后再真正执行
- 不要靠权限一刀切替代确认流程

### 6. `admin_api.py` — 管理后端（FastAPI）

```
# 部门管理
GET    /admin/depts
POST   /admin/depts
PATCH  /admin/depts/{code}
DELETE /admin/depts/{code}

# 策略管理
GET    /admin/policies?type=&level=&dept=
GET    /admin/policies/{name}
POST   /admin/policies
PATCH  /admin/policies/{name}
DELETE /admin/policies/{name}
POST   /admin/policies/{name}/toggle
GET    /admin/policies/{name}/history
GET    /admin/policies/version

# 全局变更历史
GET    /admin/audit/changes?limit=&from=&to=
```

接口要求：

- Bearer Token 鉴权，token 解出 `User` 注入
- 非 admin 角色一律 403
- 所有变更接口的 `reason` 字段必填，缺失返回 400
- 标准 JSON 响应，错误用 HTTP 状态码 + `{error, message}`

### 7. `admin.html` — 管理界面（单文件最小实现）

。包含以下功能：

- **策略列表页**：表格展示，支持按 type/level/dept 筛选；每行有编辑、启用/停用、删除按钮
- **策略编辑表单**（弹窗）：
  - 必填：name、display_name、type、level
  - level 选 `internal` 时显示部门多选
  - level 选 `restricted` 时显示部门多选 + 角色多选 + write/require_confirm 开关
  - 提交时 `reason` 必填
- **部门管理页**：增删改查
- **变更历史页**：按时间倒序展示，可按 policy 名筛选

样式**追求能用而不是好看**。

## 实现要求

- 语言：Python
- 依赖：沿用现有依赖，不要引入 OPA/Cedar
- 单元测试覆盖至少这些场景：
  1. 跨部门越权被拒
  2. 角色不足被拒
  3. 写操作拦截
  4. 知识库 metadata 过滤
  5. 审计日志完整记录拒绝请求
  6. 缓存在策略变更后正确失效
  7. 非 admin 调用管理 API 返回 403
  8. 变更不带 reason 返回 400
- 提供 `example_agent.py` 演示完整链路：用户请求 → 身份注入 → 能力过滤 → LLM 规划 → 工具调用 → 审计落盘
- 提供 `seed_demo.py` 脚本，给空数据库塞几条示例策略和部门，方便上手演示
- README 写清楚部署步骤、如何首次创建 admin 账号、如何接入企业 IdP

## 不要做的事

- ❌ 不要在 prompt 里写「你不能调用 X 工具」这种软约束
- ❌ 不要给每个 skill 内部加权限判断代码，统一在 gatekeeper 做
- ❌ 不要为不同部门建独立的向量库
- ❌ 不要引入复杂的策略引擎
- ❌ 不要把权限和业务逻辑耦合
- ❌ 不要引入 React/Vue，管理界面就单文件 HTML
- ❌ 不要做用户管理模块，用户身份从外部 IdP 来

## Plan 阶段需要输出

1. 完整文件树
2. 每个模块的关键函数签名和职责
3. 数据库 schema 最终版（可以在我给的基础上优化）
4. 三个核心流程图（文字描述即可）：
   - 用户请求 → 权限过滤 → 工具调用 的完整链路
   - 管理员修改策略 → 缓存失效 → 全节点生效 的链路
   - 敏感操作的二次确认链路
5. 测试用例清单
6. 潜在风险点和你的处理方案

输出 plan 后等我确认，我说 OK 再开始实现。
