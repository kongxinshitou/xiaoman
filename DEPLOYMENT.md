# 晓曼 Xiaoman — 云服务器部署教程

> 适用场景：将项目部署到云服务器（腾讯云 / 阿里云 / 华为云等），通过 `http://IP:8080` 访问。
> 服务器系统推荐：Ubuntu 22.04 LTS

---

## 部署架构

```
用户浏览器
    │
    ▼ http://<服务器IP>:8080
┌─────────────────────────────┐
│   Frontend 容器（Nginx）     │
│   - 托管 React 静态文件      │
│   - 代理 /api/* → 后端       │
└──────────────┬──────────────┘
               │ 容器内部网络
               ▼
┌─────────────────────────────┐
│   Backend 容器（Uvicorn）    │
│   - FastAPI :8000            │
│   - 不对外暴露端口           │
└─────────────────────────────┘
```

---

## 前置准备

### 云服务器安全组 / 防火墙

登录云服务商控制台，在安全组中**放开以下端口**：

| 端口 | 协议 | 说明 |
|------|------|------|
| 22   | TCP  | SSH 登录（一般已开） |
| 8080 | TCP  | 晓曼 Web 访问入口 |

> `:8000` 无需开放，后端只在容器内部通信。

---

## 第一步：安装 Docker

SSH 登录服务器后执行：

```bash
# 一键安装 Docker（官方脚本，适用于 Ubuntu/Debian/CentOS）
curl -fsSL https://get.docker.com | sh

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER

# 使用户组变更立即生效
newgrp docker

# 验证安装成功
docker --version
docker compose version
```

---

## 第二步：上传项目到服务器

**方式 A：通过 Git 克隆（推荐）**

```bash
# 安装 git（如未安装）
sudo apt install -y git

# 克隆项目到 /opt/xiaoman
git clone <你的仓库地址> /opt/xiaoman
cd /opt/xiaoman
```

**方式 B：本地打包上传**

```bash
# 在本地执行（Windows 用 Git Bash 或 WSL）
scp -r ./xiaoman root@<服务器IP>:/opt/xiaoman
```

---

## 第三步：创建生产环境配置

```bash
cd /opt/xiaoman

# 基于模板创建生产配置文件
cp .env.example .env.production

# 编辑配置（用 nano 或 vim）
nano .env.production
```

**需要修改的内容（最少改这一行）：**

```env
# 将 <你的服务器IP> 替换为真实公网 IP，例如：
ALLOWED_ORIGINS=["http://123.456.789.0:8080"]
```

**完整 `.env.production` 参考：**

```env
# CORS 允许来源（必填，填入服务器公网 IP + 端口）
ALLOWED_ORIGINS=["http://<你的服务器IP>:8080"]

# 文件上传限制
UPLOAD_DIR=/app/uploads
MAX_FILE_SIZE_MB=50

# 向量数据库（默认 ChromaDB，无需修改）
USE_MILVUS=false
EMBED_MODEL=text2vec-base-chinese

# 飞书集成（暂不使用则留空）
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
```

> **注意**：`SECRET_KEY` 和 `ENCRYPTION_KEY` 无需填写，容器**首次启动时会自动生成强密钥**并保存，重启后不会变化。

---

## 第四步：构建并启动

```bash
cd /opt/xiaoman

# 构建镜像并在后台启动所有容器
# 首次构建需要下载依赖，约 5~15 分钟，请耐心等待
docker compose -f docker-compose.prod.yml up -d --build
```

**构建过程说明：**

| 阶段 | 耗时估计 | 说明 |
|------|---------|------|
| 拉取基础镜像 | 1~3 min | python:3.11-slim、node:20-alpine、nginx:alpine |
| 后端安装 Python 依赖 | 3~8 min | chromadb、langchain 等包较大 |
| 前端 npm 安装 + 构建 | 1~3 min | React 编译打包 |

---

## 第五步：验证部署

```bash
# 查看容器运行状态（两个容器均应为 Up 状态）
docker compose -f docker-compose.prod.yml ps

# 查看后端日志（确认无报错）
docker compose -f docker-compose.prod.yml logs backend --tail=50

# 在服务器上测试 API 是否可达
curl http://localhost:8080/api/
# 期望返回：{"message":"晓曼 Xiaoman API","version":"1.0.0"}
```

**浏览器访问：**

```
http://<你的服务器公网IP>:8080
```

---

## 常用运维命令

### 查看状态

```bash
# 查看所有容器状态
docker compose -f docker-compose.prod.yml ps

# 实时查看所有日志
docker compose -f docker-compose.prod.yml logs -f

# 只看后端日志
docker compose -f docker-compose.prod.yml logs -f backend

# 只看前端日志
docker compose -f docker-compose.prod.yml logs -f frontend
```

### 重启服务

```bash
# 重启所有服务
docker compose -f docker-compose.prod.yml restart

# 只重启后端
docker compose -f docker-compose.prod.yml restart backend
```

### 更新代码后重新部署

```bash
cd /opt/xiaoman

# 拉取最新代码
git pull

# 重新构建并滚动替换容器（不删除数据卷）
docker compose -f docker-compose.prod.yml up -d --build
```

### 停止服务

```bash
# 停止并移除容器（保留数据卷）
docker compose -f docker-compose.prod.yml down

# 停止并移除容器 + 数据卷（⚠️ 慎用：会清空上传文件、向量数据库）
docker compose -f docker-compose.prod.yml down -v
```

### 进入容器调试

```bash
# 进入后端容器
docker exec -it xiaoman-backend bash

# 进入前端容器
docker exec -it xiaoman-frontend sh
```

---

## 数据持久化说明

项目使用 Docker 卷保存以下数据，**停止容器不会丢失**：

| 卷名 | 对应路径 | 内容 |
|------|---------|------|
| `xiaoman_uploads` | `/app/uploads` | 用户上传的文件 |
| `xiaoman_chroma` | `/app/chroma_data` | 知识库向量索引 |
| `xiaoman_secrets` | `/secrets` | 自动生成的密钥 |

**查看卷位置：**

```bash
docker volume inspect xiaoman_xiaoman_secrets
```

**备份上传文件：**

```bash
# 将上传文件备份到宿主机
docker cp xiaoman-backend:/app/uploads ./backup_uploads
```

> ⚠️ **重要**：`xiaoman_secrets` 卷存储着 JWT 密钥和加密密钥，不要执行 `docker compose down -v`，否则所有用户需重新登录，且加密数据无法解密。

---

## 常见问题排查

### 问题 1：容器启动后 `backend` 一直在重启

```bash
# 查看详细错误日志
docker compose -f docker-compose.prod.yml logs backend
```

常见原因：
- `.env.production` 文件不存在 → 检查是否已创建
- `ALLOWED_ORIGINS` 格式错误 → 确保是 JSON 数组格式：`["http://IP:8080"]`

### 问题 2：前端页面打开了但 API 请求报错 / 登录失败

```bash
# 检查后端是否健康
curl http://localhost:8080/api/

# 检查后端日志
docker compose -f docker-compose.prod.yml logs backend --tail=100
```

常见原因：
- CORS 配置错误：`ALLOWED_ORIGINS` 中的 IP 与实际访问 IP 不匹配

### 问题 3：AI 对话没有流式输出，等很久才一次性返回

原因：Nginx 的 `proxy_buffering` 配置未生效。确认 `nginx/xiaoman.conf` 中包含：

```nginx
proxy_buffering    off;
proxy_read_timeout 300s;
```

然后重启前端容器：

```bash
docker compose -f docker-compose.prod.yml restart frontend
```

### 问题 4：首次启动后端 healthcheck 失败，前端迟迟不启动

ChromaDB 首次加载嵌入模型需要 30~60 秒，这是正常现象。等待约 1 分钟后再检查：

```bash
docker compose -f docker-compose.prod.yml ps
```

### 问题 5：端口 8080 无法访问

1. 检查容器是否正常运行：`docker compose -f docker-compose.prod.yml ps`
2. 检查云服务器**安全组**是否放开了 8080 端口
3. 检查服务器本地防火墙：

```bash
# Ubuntu 查看防火墙状态
sudo ufw status

# 如果防火墙开启，放行 8080
sudo ufw allow 8080/tcp
```

---

## 目录结构参考

```
xiaoman/
├── backend/
│   ├── .dockerignore       # Docker 构建忽略文件
│   ├── Dockerfile          # 后端镜像构建文件
│   ├── entrypoint.sh       # 容器启动脚本（自动生成密钥）
│   ├── requirements.txt    # Python 依赖
│   └── app/                # FastAPI 应用代码
├── frontend/
│   ├── .dockerignore       # Docker 构建忽略文件
│   ├── Dockerfile          # 前端多阶段构建文件
│   └── src/                # React 源码
├── nginx/
│   └── xiaoman.conf        # Nginx 反向代理配置
├── docker-compose.yml      # 开发环境编排
├── docker-compose.prod.yml # 生产环境编排（部署用这个）
├── .env.example            # 环境变量模板
└── .env.production         # 生产环境变量（服务器上手动创建）
```

---

*生成日期：2026-04-07*
