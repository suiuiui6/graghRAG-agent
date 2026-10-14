# MinerU MVP 测试 — CLAUDE.md

## 项目概述

MinerU MVP 测试项目用于验证 MinerU 云端 API 的文档解析能力，
作为 GraphRAG 系统中文档解析层的前置服务。

## 必读：虚拟环境隔离规范

本项目采用 `uv` 管理独立的 Python 虚拟环境，与 LangExtract 及其他
组件完全隔离，避免依赖冲突。

### 激活虚拟环境（执行任何操作前必须先执行）

**Windows (Git Bash / WSL):**
```bash
source D:/graghRAG-agent/mineru-mvp-test/.venv/Scripts/activate
```

**Windows (CMD):**
```cmd
D:\graghRAG-agent\mineru-mvp-test\.venv\Scripts\activate.bat
```

**Windows (PowerShell):**
```powershell
D:\graghRAG-agent\mineru-mvp-test\.venv\Scripts\Activate.ps1
```

### 验证环境已激活

```bash
python -c "import sys; print(sys.prefix)"
# 应输出: D:\graghRAG-agent\mineru-mvp-test\.venv
```

### 首次创建环境

```bash
cd D:/graghRAG-agent/mineru-mvp-test
uv venv .venv --python 3.12
source .venv/Scripts/activate
uv pip install -r requirements.txt
```

## 项目文件结构

```
mineru-mvp-test/
├── .venv/                    ← uv 虚拟环境（独立隔离）
├── .env                      ← API Token + 解析参数配置
├── .env.example              ← 配置模板（可提交 git）
├── .gitignore                ← 排除 .venv/ .env output/
├── CLAUDE.md                 ← 本文件 — 项目规范说明
├── requirements.txt          ← Python 依赖（含 fpdf2）
├── generate_sample_pdf.py    ← 生成示例 PDF
├── run_mvp.py                ← MVP Pipeline 主入口
├── sample.pdf                ← 示例 PDF 文件
├── output/                   ← MinerU API 解析结果输出
└── README.md                 ← 运行说明
```

## 环境约束规则

1. **启动前必须激活 `.venv`**：所有 `python` / `pip` / `uv pip` 命令必须在
   激活虚拟环境后执行，禁止在全局 Python 环境中安装项目依赖。

2. **`.env` 不提交 git**：Token 等敏感配置仅存于 `.env`（已在 `.gitignore` 排除）。

3. **依赖变更流程**：修改 `requirements.txt` 后，执行：
   ```bash
   source .venv/Scripts/activate
   uv pip install -r requirements.txt
   ```

4. **Python 版本要求**：`>= 3.10`，环境创建时指定 `--python 3.12`。

## 与 LangExtract 的隔离关系

```
D:\graghRAG-agent\
├── langextract\              ← LangExtract 项目（独立 Python 环境）
│   └── .venv\                ← LangExtract 专用虚拟环境
├── mineru-mvp-test\          ← MinerU MVP 测试（独立 Python 环境）
│   └── .venv\                ← MinerU 专用虚拟环境（本文件管理）
```

**两个组件的虚拟环境完全独立**，各自安装自身的依赖，
不会因包版本冲突造成环境污染。

## 运行 MVP 测试

```bash
# 1. 激活环境
source D:/graghRAG-agent/mineru-mvp-test/.venv/Scripts/activate

# 2. 生成示例 PDF（首次）
python generate_sample_pdf.py

# 3. 运行 MVP Pipeline
python run_mvp.py
```
