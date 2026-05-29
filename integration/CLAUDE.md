# BridgePipeline — CLAUDE.md

## 项目概述

BridgePipeline 是 MinerU → LangExtract 的组件对接管道，
负责将 MinerU 文档解析结果转换为 LangExtract 结构化抽取输入，
并最终生成 Knowledge Graph 的 nodes.json 和 edges.json，
作为 GraphRAG 索引阶段的核心流程。

## 必读：虚拟环境隔离规范

BridgePipeline 与 LangExtract **共用虚拟环境**。
所有 python 命令启动前必须先激活:

**Windows (Git Bash):**
```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
```

**验证环境已激活:**
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
cd D:/graghRAG-agent/integration
uv pip install pyyaml
```

## 项目文件结构

```
integration/
├── .env                                ← 合并 MinerU + LangExtract 配置
├── CLAUDE.md                           ← 本文件
├── pipeline.py                         ← 主 Pipeline 编排器
├── bridge.py                           ← Format Bridge (section分段 + PositionMap)
├── grounding.py                        ← 溯源解析 (char → bbox + page)
├── kg_builder.py                       ← KG 构建 (node + edge)
├── schema.py                           ← 数据类定义
├── config/
│   └── extraction_examples.yaml        ← Few-shot 示例 (4 examples)
└── output/kg/
    ├── nodes.json                      ← KG 节点
    ├── edges.json                      ← KG 边
    └── integrated_*.jsonl              ← 中间 JSONL
```

## 组件隔离架构

```
D:\graghRAG-agent\
├── integration\                        ← BridgePipeline (共用 langextract .venv)
├── langextract\
│   └── .venv\                          ← 63 个包, Python 3.12.8 (★ BridgePipeline 使用此环境)
└── mineru-mvp-test\
    └── .venv\                          ← 10 个包, Python 3.12.8 (MinerU 专用)
```

BridgePipeline 通过 `curl` 子进程调用 MinerU API，MinerU 的 .venv 仅在手动运行 `run_mvp.py` 时使用。

## 运行方式

### 跳过 MinerU (推荐: 使用缓存解析结果)

```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
cd D:/graghRAG-agent/integration
python pipeline.py --cached ../mineru-mvp-test/output/87bc1f56
```

### 完整流程 (MinerU 解析 + KG)

```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
cd D:/graghRAG-agent/integration
python pipeline.py --pdf ../mineru-mvp-test/sample.pdf
```

## 环境约束规则

1. **启动前必须激活 `langextract/.venv`** — 所有 python 命令必须在激活后执行
2. **`.env` 不提交 git** — API Key 和 Token 为敏感信息
3. **MinerU 通过 curl 调用** — 不依赖 mineru-mvp-test/.venv
4. **Python >= 3.10** — 环境使用 3.12
5. **依赖变更**: `source D:/graghRAG-agent/langextract/.venv/Scripts/activate && uv pip install <pkg>`

## 规范文档索引

- BridgePipeline 规范: `../langextract/docs/bridge-pipeline-specification-v1.0.md`
- LangExtract 规范: `../langextract/docs/LangExtract-Pipeline-Specification.md`
- MinerU 规范: `../langextract/docs/MinerU_MVP测试配置指南.md_v1.0.md`
