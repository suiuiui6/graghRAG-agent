# Backend — CLAUDE.md

## 项目概述

GraphRAG 多模态知识图谱问答系统后端服务。
FastAPI + LangGraph Agent + DeepSeek，提供 RESTful API。

## 启动方式

```bash
# 1. 激活虚拟环境
source D:/graghRAG-agent/backend/.venv/Scripts/activate

# 2. 进入后端目录
cd D:/graghRAG-agent/backend

# 3. 启动服务 (端口 8000)
uvicorn server:app --host 0.0.0.0 --port 8000 --reload --limit-max-requests 0 --timeout-keep-alive 300
```

## API 端点

| Method | Path | 说明 |
|---|---|---|
| GET | `/` | 服务信息 |
| GET | `/docs` | Swagger UI |
| POST | `/api/v1/ingest` | 上传文档并触发索引 |
| GET | `/api/v1/status/{task_id}` | 查询索引进度 |
| POST | `/api/v1/query` | KG 知识图谱问答 |
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/documents` | 已索引文档列表 |
| DELETE | `/api/v1/documents/{doc_id}` | 删除文档 |

## 环境要求

- Python 3.12 (uv 虚拟环境)
- `.env` 文件已配置 DeepSeek API Key
- KG 数据位于 `output/kg/` (nodes.json + edges.json)
