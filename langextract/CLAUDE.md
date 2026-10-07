# LangExtract — CLAUDE.md

## 项目概述

LangExtract 是 Google 开源的基于 LLM 的结构化信息抽取库，
在 GraphRAG 系统中充当数据抽取后端服务。

## 必读：虚拟环境隔离规范

本项目采用 `uv` 管理独立的 Python 虚拟环境，与 MinerU 及其他
组件完全隔离，避免依赖冲突。

### 激活虚拟环境（执行任何操作前必须先执行）

**Windows (Git Bash / WSL):**
```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
```

**Windows (CMD):**
```cmd
D:\graghRAG-agent\langextract\.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
D:\graghRAG-agent\langextract\.venv\Scripts\Activate.ps1
```

### 验证环境已激活

```bash
python -c "import sys; print(sys.prefix)"
# 应输出: D:\graghRAG-agent\langextract\.venv
```

### 首次创建环境

```bash
cd D:/graghRAG-agent/langextract
uv venv .venv --python 3.12
source .venv/Scripts/activate
uv pip install -e ".[test]"
```

## 项目文件结构

```
langextract/
├── .venv/                         ← uv 虚拟环境（独立隔离）
├── .env                           ← API Key 配置（.gitignore 排除）
├── .gitignore                     ← 排除 .venv/ .env
├── CLAUDE.md                      ← 本文件 — 项目规范说明
├── pyproject.toml                 ← 项目元数据与依赖声明
├── langextract/                   ← 核心源码
│   ├── __init__.py                ← 主入口 (lx.extract / lx.visualize)
│   ├── extraction.py              ← 抽取 Pipeline
│   ├── chunking.py                ← 文本分块
│   ├── annotation.py              ← 标注引擎
│   ├── resolver.py                ← LLM 输出解析与对齐
│   ├── prompting.py               ← Prompt 构建
│   ├── factory.py                 ← 模型工厂
│   ├── io.py                      ← 输入输出 (JSONL/CSV)
│   ├── visualization.py           ← 交互式 HTML 可视化
│   ├── core/                      ← 核心数据类型与抽象
│   └── providers/                 ← LLM 提供商 (Gemini/OpenAI/Ollama)
├── tests/                         ← 测试用例
├── docs/                          ← 规范文档
│   ├── LangExtract-Pipeline-Specification.md
│   ├── MinerU-API-Specification.md
│   └── MinerU_MVP测试配置指南.md_v1.0.md
└── examples/                      ← 使用示例
```

## 环境约束规则

1. **启动前必须激活 `.venv`**：所有 `python` / `pip` / `pytest` 命令必须在
   激活虚拟环境后执行。

2. **API Key 配置**：通过环境变量 `LANGEXTRACT_API_KEY` 或
   `.env` 文件设置（已在 `.gitignore` 排除）。

3. **依赖变更流程**：
   ```bash
   source .venv/Scripts/activate
   uv pip install -e ".[test]"
   ```

4. **Python 版本要求**：`>= 3.10`，环境创建时指定 `--python 3.12`。

## 与 MinerU 的隔离关系

```
D:\graghRAG-agent\
├── langextract\                   ← LangExtract（独立 .venv）
│   └── .venv\                     ← # LangExtract 专用虚拟环境
└── mineru-mvp-test\               ← MinerU MVP（独立 .venv）
    └── .venv\                     ← # MinerU 专用虚拟环境
```

**两个组件的虚拟环境完全独立**，LangExtract 依赖 `google-genai>=1.39.0`、
`pandas>=1.3.0` 等 63 个包，与 MinerU 的 fpdf2/requests 环境互不干扰。

## 功能测试运行

```bash
# 1. 激活环境
source D:/graghRAG-agent/langextract/.venv/Scripts/activate

# 2. 运行测试套件
pytest tests/ -v

# 3. 运行特定测试
pytest tests/inference_test.py -v
pytest tests/schema_test.py -v
pytest tests/factory_test.py -v

# 4. 运行基础功能验证
python -c "
import langextract as lx
print('LangExtract loaded successfully')
print('Available:', dir(lx))
"
```
