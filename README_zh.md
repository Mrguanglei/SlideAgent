# 👋 Hi～ SlideAgent - 让PPT生成更加简单

[![English](https://img.shields.io/badge/README-English-blue.svg)](README.md) | [中文](README_zh.md)

**SlideAgent** 是一款开源的 AI 驱动的演示文稿生成工具。只需输入您的想法，即可自动生成精美的 PPT，支持多种导出格式和在线分享。

# 创作不易，多多Star ✨ ✨ ✨ ✨ ✨

![PPTAgent主页](images/home.png)

## ⚠️注意：本项目是基于[PPTAgent (CAS)](https://github.com/icip-cas/PPTAgent)此开源项目二次开发,代码部分依旧保持 PPTAgent命名

## ✨ 主要功能

| 功能 | 状态 | 描述 |
| :--- | :--- | :--- |
| **AI 生成 PPT** | ✅ | 基于大语言模型，自动生成大纲、内容和设计 |
| **在线分享** | ✅ | 生成分享链接，支持设置有效期 |
| **全局搜索** | ✅ | 快速搜索对话历史和 PPT 项目 |
| **知识库** | ✅ | 上传文档，基于知识库内容生成 PPT |
| **任务队列** | ✅ | 批量上传文档，后端自动排队处理 |

## ✨ TODO

- [x] **内容编辑** - 直接在预览页面编辑文本内容
- [x] **在线预览** - 在浏览器中实时预览 PPT 效果
- [x] **下载导出** - 支持导出为 PDF、PNG (ZIP)、PPTX 格式. Note:样式会丢失，正在处理
- [ ] **对话式编辑** - 通过对话持续修改和优化 PPT 内容
- [ ] **多版本管理** - 保存历史版本，随时回滚和比较
- [ ] **状态管理** - Agent任务状态全局持久化设计

## 🚀 快速开始

### 前置条件

- Docker 和 Docker Compose
- Git

### 使用 Docker Compose 运行

1. **克隆仓库**
   ```bash
   git clone https://github.com/Mrguanglei/SlideAgent.git
   cd SlideAgent
   ```

2. **配置 (可选)**
   复制 `.env.example` 为 `.env` 并按需修改：
   ```bash
   cp .env.example .env
   ```
   您可以在 `.env` 文件中配置数据库、LLM API Key 等。

3. **构建并启动服务**
   ```bash
   docker-compose up --build -d
   ```

4. **访问应用**
   - **前端:** [http://localhost:3000](http://localhost:3000)
   - **后端 API:** [http://localhost:8000/docs](http://localhost:8000/docs)

## 📸 界面截图

| 主页 | 对话生成 |
| :--- | :--- |
| ![主页](images/home.png) | ![对话生成](images/chat.png) |
| **知识库** | **全局搜索** |
| ![知识库](images/knowledge.png) | ![全局搜索](images/search.png) |


## 🛠️ 项目结构

```
.env.example         # 环境变量示例
docker-compose.yml   # Docker 编排配置
README.md            # 项目说明

backend/             # Python 后端 (FastAPI)
├── services/        # 核心服务（导出、分享、知识库）
├── routers/         # API 路由
├── database/        # 数据库模型和 CRUD
├── api_server.py    # FastAPI 服务器入口
├── requirements.txt # Python 依赖
└── Dockerfile

frontend/            # React 前端 (Vite)
├── src/
│   ├── pages/       # 页面组件 (Home, Knowledge, ShareView)
│   ├── components/  # 可复用组件 (Sidebar, Modals, etc.)
│   ├── lib/         # API 请求、工具函数
│   └── types/       # TypeScript 类型定义
├── package.json     # Node.js 依赖
├── vite.config.ts   # Vite 配置
└── Dockerfile
```

## ⚙️ 环境变量

在项目根目录创建 `.env` 文件以覆盖默认配置。

| 变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `POSTGRES_DB` | `pptagent` | 数据库名称 |
| `POSTGRES_USER` | `pptagent` | 数据库用户名 |
| `POSTGRES_PASSWORD` | `pptagent` | 数据库密码 |
| `DATABASE_URL` | `postgresql+asyncpg://...` | 数据库连接字符串 |
| `PPTAGENT_API_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4/` | PPT 生成 LLM API 地址 |
| `PPTAGENT_API_KEY` | `your_api_key` | PPT 生成 LLM API Key |
| `PPTAGENT_MODEL` | `glm-4-flash` | PPT 生成 LLM 模型 |
| `KNOWLEDGE_LLM_BASE_URL` | `PPTAGENT_API_BASE_URL` | 知识库 LLM API 地址 |
| `KNOWLEDGE_LLM_API_KEY` | `PPTAGENT_API_KEY` | 知识库 LLM API Key |
| `KNOWLEDGE_LLM_MODEL` | `glm-4-flash` | 知识库 LLM 模型 |
| `KNOWLEDGE_EMBEDDING_MODEL` | `embedding-3` | 知识库向量化模型 |
| `KNOWLEDGE_UPLOAD_DIR` | `/tmp/knowledge_uploads` | 知识库文件上传目录 |

## 🤝 贡献

欢迎各种形式的贡献！如果您有任何想法或建议，请随时提交 Pull Request 或创建 Issue。


[![Star History Chart](https://api.star-history.com/svg?repos=Mrguanglei/SlideAgent&type=Date)](https://star-history.com/#Mrguanglei/SlideAgent&Date)


## 🙏 致谢

- [PPTAgent (CAS)](https://github.com/icip-cas/PPTAgent) - 本项目基于此开源项目二次开发，感谢原作者的贡献。
- [shadcn/ui](https://ui.shadcn.com/) - 前端 UI 组件库。
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能的 Python Web 框架。
- [React](https://react.dev/) - 用于构建用户界面的 JavaScript 库。

## 📄 许可证

本项目遵循 **[AGPL-3.0 协议](https://www.gnu.org/licenses/agpl-3.0.html)**。仅供学习和交流使用，禁止用于任何商业目的。
