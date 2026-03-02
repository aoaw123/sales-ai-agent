# 智能销售 AI Agent 🤖

基于 **FastAPI + LangGraph** 的智能销售助手后端服务，支持文档自动生成、产品知识问答、销售话术辅助等功能。

## ✨ 功能特性

| 功能 | 描述 | 技术实现 |
|------|------|----------|
| 💬 智能对话 | 多轮对话，上下文理解 | LangGraph StateGraph |
| 🔍 知识问答 | RAG 检索增强的产品咨询 | FAISS + OpenAI Embeddings |
| 📄 报价单生成 | 自动创建 Excel 报价单 | openpyxl |
| 📋 提案书生成 | 自动生成 Word 提案书 | python-docx |
| 📝 合同起草 | 智能合同模板生成 | python-docx |
| 📊 数据报表 | 销售数据分析报表 | openpyxl |
| 📽️ 演示文稿 | PPT 大纲自动生成 | python-pptx |
| 💰 价格谈判 | 销售话术辅助 | LLM Prompt Engineering |
| 😊 投诉处理 | 客户服务话术支持 | LLM Prompt Engineering |

## 🏗️ 项目架构

```
sales-ai-agent/
├── app/
│   ├── api/                    # API 路由
│   │   ├── v1/
│   │   │   ├── chat.py        # 核心对话接口
│   │   │   └── documents.py   # 文档管理接口
│   │   └── deps.py            # 依赖注入
│   ├── core/                   # 核心模块
│   │   ├── config.py          # 配置管理
│   │   ├── logging.py         # 日志配置
│   │   └── exceptions.py      # 自定义异常
│   ├── models/                 # 数据模型
│   │   └── chat.py            # Pydantic 模型
│   ├── agents/                 # LangGraph 工作流
│   │   ├── state.py           # State 定义
│   │   ├── graphs/
│   │   │   └── sales_graph.py # 主工作流图
│   │   └── nodes/             # 工作流节点
│   │       ├── intent_node.py         # 意图识别
│   │       ├── knowledge_node.py      # RAG 检索
│   │       ├── document_nodes.py      # 文档生成
│   │       └── response_node.py       # 销售回复
│   └── main.py                # FastAPI 入口
├── skills/                     # 本地技能集成（你的 skills）
├── data/                       # 数据目录
│   ├── knowledge_base/        # 知识库文件
│   └── vector_store/          # 向量数据库
├── output/                     # 生成文档输出目录
├── tests/                      # 测试用例
├── requirements.txt            # Python 依赖
├── .env.example               # 环境变量示例
├── run.py                     # 启动脚本
└── README.md                  # 本文档
```

## 🚀 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 16+（用于部分文档生成技能）
- LibreOffice（可选，用于文档格式转换）

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv

# 激活环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env 文件，填写你的 API Key
vim .env
```

必须配置的变量：
```env
OPENAI_API_KEY=sk-your-api-key
# 或
OPENAI_BASE_URL=https://api.moonshot.cn/v1  # 如果使用 Moonshot
OPENAI_API_KEY=sk-your-moonshot-key
```

### 4. 启动服务

```bash
# 开发模式（自动重载）
python run.py

# 或指定端口
python run.py --port 8080

# 生产模式
python run.py --prod --workers 4
```

服务启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 📡 API 接口

### 核心对话接口

```http
POST /api/v1/chat
Content-Type: application/json

{
    "session_id": "wx_user_123",
    "message": "帮我生成一份报价单",
    "history": [],
    "context": {
        "customer_name": "张三科技",
        "sales_rep_name": "李明"
    }
}
```

响应示例：

```json
{
    "session_id": "wx_user_123",
    "reply": "好的，请提供以下信息：产品清单、数量...",
    "intent": "quote_generation",
    "documents": [],
    "suggested_actions": ["提供产品清单", "查看模板"],
    "metadata": {
        "knowledge_results_count": 0,
        "document_params": {...}
    },
    "response_time_ms": 1250
}
```

### 文档下载

```http
GET /api/v1/docs/documents/报价单_张三科技_20240228.xlsx
```

## 🔧 集成你的本地 Skills

本项目已预留与本地 skills 的集成接口：

### 1. 文档生成技能（已内置）

```python
# app/agents/nodes/document_nodes.py

# Excel 生成（基于 xlsx skill 的技术栈）
from openpyxl import Workbook

# Word 生成（基于 docx skill 的技术栈）  
from docx import Document

# PPT 生成（基于 pptx skill 的技术栈）
from pptx import Presentation
```

### 2. 进阶集成方式

如需调用 Node.js 版本的技能脚本：

```python
import subprocess

# 调用 docx-js 生成复杂文档
subprocess.run([
    "node", "skills/docx/generate.js",
    "--template", "proposal",
    "--output", "output.docx"
])
```

## 🧪 测试

```bash
# 运行测试
pytest tests/

# 运行特定测试
pytest tests/test_chat.py -v

# 覆盖率报告
pytest --cov=app tests/
```

## 📝 开发计划

- [x] 基础架构搭建
- [x] LangGraph 工作流设计
- [x] 意图识别节点
- [x] 知识库 RAG 节点
- [x] 文档生成节点
- [x] FastAPI 接口
- [ ] WebSocket 流式响应
- [ ] 微信小程序登录集成
- [ ] 数据库持久化
- [ ] 知识库管理界面

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支：`git checkout -b feature/xxx`
3. 提交更改：`git commit -am 'Add xxx'`
4. 推送分支：`git push origin feature/xxx`
5. 创建 Pull Request

## 📄 许可证

MIT License

## 📞 联系方式

如有问题或建议，欢迎提交 Issue 或 PR。
