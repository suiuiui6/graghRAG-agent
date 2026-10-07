# BridgePipeline 规范文档 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24 | **状态**: ✅ 已通过端到端实测验证
>
> 本文档定义 MinerU → LangExtract 组件对接的 BridgePipeline 完整规范，
> 该流程作为 GraphRAG 索引阶段的核心流程。

---

## 目录

1. [BridgePipeline 执行流程](#1-bridgepipeline-执行流程)
2. [测试脚本存放路径](#2-测试脚本存放路径)
3. [本地实测输出规范](#3-本地实测输出规范)
4. [MinerU 关键参数规范](#4-mineru-关键参数规范)
5. [LangExtract 关键参数规范](#5-langextract-关键参数规范)
6. [组件接口对接规范](#6-组件接口对接规范)
7. [BridgePipeline 输出参数规范](#7-bridgepipeline-输出参数规范)
8. [运行环境与 CLAUDE.md](#8-运行环境与-claudemd)

---

## 1. BridgePipeline 执行流程

### 1.1 总体架构

```
                         BridgePipeline (6 Stages)
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Stage 1    Stage 2       Stage 3         Stage 4     Stage 5        │
│  ────────   ────────────  ──────────────  ──────────  ────────────   │
│  MinerU  →  Format Bridge → LangExtract  → Grounding → KG Builder    │
│  解析       section分段     DeepSeek抽取    溯源解析    图谱构建       │
│                                                                      │
│  Input:    Output:        Output:         Output:     Output:         │
│  PDF/DOCX  list[Document] list[Annotated  list[       nodes.json     │
│            +PositionMap   Document]       Grounded    +edges.json     │
│                                           Extraction]                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 各 Stage 详解

#### Stage 1: MinerU 文档解析

```
本地 PDF/DOCX → 上传至公网 → POST /api/v4/extract/task → 轮询 state → 下载 ZIP → 解压
```

**输入**: 本地文件路径或公网 URL
**输出**: `full.md` + `{uuid}_content_list.json` + `layout.json` + `images/`
**关键决策**: 若 `FILE_URL` 已设置则直接使用；否则尝试 file.io/transfer.sh 上传
**容错**: HTTP 429 指数退避重试 (max 3 次)；state=failed 时捕获 err_msg

#### Stage 2: Format Bridge

```
content_list.json → 提取 text_level=1,2 → section 边界 → full.md 分段 → list[Document]
                  → 逐 item 文本匹配 full.md → PositionMap
```

**关键决策**:
- 按 H1/H2 标题边界预分段，每 section 一个 Document
- 最小 section 合并：< 150 chars 合并到前一 section
- PositionMap 记录 full.md 中每个 segment 对应的 content_list item (bbox + page_idx + block_type)

#### Stage 3: LangExtract 抽取

```
list[Document] + extraction_examples.yaml + prompt_description
    → use_schema_constraints=False, fence_output=True
    → DeepSeek API (https://api.deepseek.com)
    → list[AnnotatedDocument]
```

**关键决策**: DeepSeek 不支持 JSON mode，降级为 YAML fence 解析
**容错**: 单 chunk 解析失败自动跳过 (suppress_parse_errors=True)，单 document 失败不阻塞其余

#### Stage 4: Grounding 溯源解析

```
Extraction.char_interval (relative)
    → + section 起始偏移 → full.md 全局位置
    → PositionMap.lookup_range()
    → bbox (0-1000 归一化) + page_idx + block_type
```

**关键决策**: 两级映射 (Document offset → full.md global → content_list item)
**未接地处理**: `char_interval = None` → `grounding_status: "ungrounded"`, 节点仍保留

#### Stage 5: KG 图谱构建

```
GroundedExtraction[] → 每个 → 一个 KGNode (node_id + entity_type + label + properties + bbox)
                    → 启发式规则 → KGEdge (co_occurs_with / same_type / adjacent_to)
```

**边构建优先级**:
1. 同页共现 (same page_idx) → `co_occurs_with`
2. 同类型顺连 (same entity_type) → `same_type`
3. 顺序邻接 (sequential order) → `adjacent_to`

---

## 2. 测试脚本存放路径

### 2.1 集成项目完整文件树

```
D:\graghRAG-agent\integration\
├── .env                                    ← 合并 MinerU + LangExtract 配置
├── pipeline.py                             ← ★ 主编排器 (5 个 Stage 入口)
├── bridge.py                               ← Stage 2: Format Bridge
├── grounding.py                            ← Stage 4: 溯源解析
├── kg_builder.py                           ← Stage 5: KG 构建
├── schema.py                               ← 数据模型定义
├── config/
│   └── extraction_examples.yaml            ← Few-shot 示例 (4 examples, 11 entity types)
└── output/
    └── kg/
        ├── nodes.json                      ← KG 节点输出 (~119 KB)
        ├── edges.json                      ← KG 边输出 (~360 KB)
        └── integrated_*.jsonl              ← 中间 JSONL (LangExtract raw output)
```

### 2.2 相关组件路径

| 组件 | 路径 | 说明 |
|---|---|---|
| MinerU MVP | `D:\graghRAG-agent\mineru-mvp-test\` | 独立 .venv, 含 run_mvp.py |
| MinerU 缓存 | `D:\graghRAG-agent\mineru-mvp-test\output\87bc1f56\` | arXiv Transformer 论文解析结果 |
| LangExtract | `D:\graghRAG-agent\langextract\` | 独立 .venv, 含 mvp_deepseek_test.py |
| LangExtract 规范 | `D:\graghRAG-agent\langextract\docs\LangExtract-Pipeline-Specification.md` | 抽取规范 |
| MinerU 规范 | `D:\graghRAG-agent\langextract\docs\MinerU_MVP测试配置指南.md_v1.0.md` | 解析规范 |
| **BridgePipeline 规范** | `D:\graghRAG-agent\langextract\docs\bridge-pipeline-specification-v1.0.md` | **本文档** |

### 2.3 运行命令

```bash
# 激活 LangExtract 虚拟环境 (BridgePipeline 共用此环境)
source D:/graghRAG-agent/langextract/.venv/Scripts/activate

cd D:/graghRAG-agent/integration

# 完整流程 (MinerU 解析 + KG)
python pipeline.py --pdf ../mineru-mvp-test/sample.pdf

# 跳过 MinerU (使用缓存结果)
python pipeline.py --cached ../mineru-mvp-test/output/87bc1f56

# 指定自定义参数
python pipeline.py --cached <path> --examples ./config/extraction_examples.yaml --output ./output/custom_kg
```

---

## 3. 本地实测输出规范

> 以下所有示例截取自 **2026-05-24 实测** (arXiv Transformer 论文, 15 页, deepseek-chat)。

### 3.1 实测统计数据

| Pipeline 指标 | 值 |
|---|---|
| MinerU 解析引擎 | pipeline |
| 输入文档 | arXiv 1706.03762v7 (15 pages) |
| full.md 长度 | 42,551 chars |
| content_list 项数 | 141 |
| 分段结果 | 24 sections (H1+H2 boundaries) |
| LangExtract 抽取总数 | 310 entities |
| 接地 (Stage 3 raw) | 276 (89.0%) |
| 接地 (Stage 4 resolved) | 214 (69.0%) |
| KG 节点数 | 310 |
| KG 边数 | 1,529 |
| 总 Pipeline 耗时 | ~49s |

### 3.2 Entity 类别分布

| entity_type | 数量 | 示例 |
|---|---|---|
| `reference` | 76 | `[13]`, `[2]` (Bahdanau et al.) |
| `claim` | 48 | "Transformer requires constant O(1) operations" |
| `model_component` | 40 | "Multi-Head Attention", "Feed-Forward network" |
| `metric` | 35 | "28.4 BLEU", "41.8 BLEU" |
| `paper_metadata` | 31 | "Attention Is All You Need", "Ashish Vaswani" |
| `method` | 23 | "Adam optimizer", "Dropout", "Label Smoothing" |
| `section_header` | 18 | "3 Model Architecture", "4 Why Self-Attention" |
| `equation` | 16 | "Attention(Q,K,V) = softmax(QK^T/sqrt(d_k))V" |
| `definition` | 13 | Self-attention, Multi-head attention definitions |
| `dataset` | 10 | "WMT 2014 English-to-German", "WMT 2014 English-to-French" |

### 3.3 KG Node 输出格式 (nodes.json)

```json
{
  "metadata": {
    "pipeline": "MinerU → LangExtract",
    "model": "deepseek-chat",
    "timestamp": "2026-05-24T16:34:51.649739"
  },
  "node_count": 310,
  "nodes": [
    {
      "node_id": "n0001",
      "entity_type": "paper_metadata",
      "label": "Attention Is All You Need",
      "properties": {
        "field": "title"
      },
      "page_idx": 0,
      "bbox_norm": [341, 184, 653, 208],
      "grounding_status": "grounded"
    }
  ]
}
```

**Node 字段规范**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `node_id` | `string` | ✅ | 唯一标识，格式 `n{0001..9999}` |
| `entity_type` | `string` | ✅ | 实体类别 (11 种枚举值) |
| `label` | `string` | ✅ | 实体文本 (来自 `extraction_text`) |
| `properties` | `dict` | ✅ | 实体属性键值对 (来自 `attributes`) |
| `page_idx` | `int \| null` | ✅ | PDF 页码 (0-based), `null` = 未接地 |
| `bbox_norm` | `[float,float,float,float] \| null` | ✅ | 0-1000 归一化包围框, `null` = 未接地 |
| `grounding_status` | `string` | ✅ | `"grounded"` \| `"ungrounded"` |

### 3.4 KG Edge 输出格式 (edges.json)

```json
{
  "edge_count": 1529,
  "edges": [
    {
      "edge_id": "e0001",
      "source_node_id": "n0001",
      "target_node_id": "n0002",
      "relation_type": "co_occurs_with",
      "properties": {
        "rule": "same_page",
        "page_idx": 0
      }
    }
  ]
}
```

**Edge 字段规范**:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `edge_id` | `string` | ✅ | 唯一标识，格式 `e{0001..9999}` |
| `source_node_id` | `string` | ✅ | 源节点 ID |
| `target_node_id` | `string` | ✅ | 目标节点 ID |
| `relation_type` | `string` | ✅ | 关系类型 (见下方枚举) |
| `properties` | `dict` | ✅ | 边属性 (含 `rule` 标识生成策略) |

**Relation 类型枚举**:

| relation_type | 生成规则 | 说明 |
|---|---|---|
| `co_occurs_with` | 同 page_idx 节点互连 | 共现关系 |
| `same_type` | 同 entity_type 节点沿序连接 | 同类关联 |
| `adjacent_to` | Pipeline 输出顺序的邻接节点 | 顺序邻接 |

### 3.5 中间 JSONL 格式 (Stage 3 输出)

```json
{
  "document_id": "sec_6_3_1_encoder_and_decoder_stacks",
  "text": "Encoder: The encoder is composed of...",
  "extractions": [
    {
      "extraction_class": "model_component",
      "extraction_text": "multi-head self-attention mechanism",
      "char_interval": {"start_pos": 125, "end_pos": 162},
      "alignment_status": "match_exact",
      "extraction_index": 0,
      "group_index": 0,
      "attributes": {"component_type": "mechanism"}
    }
  ]
}
```

---

## 4. MinerU 关键参数规范

### 4.1 提交任务参数 (POST /api/v4/extract/task)

| 参数 | 类型 | 必传 | 默认值 | 取值范围 | 说明 |
|---|---|---|---|---|---|
| **`url`** | `string` | **✅** | — | 公网 HTTP/HTTPS URL | 待解析文件地址。**不支持直接上传文件** |
| `is_ocr` | `bool` | 否 | `false` | `true` / `false` | 是否启用 OCR。扫描件/图片型 PDF **必须设 `true`** |
| `enable_formula` | `bool` | 否 | `true` | `true` / `false` | 是否识别公式并转 LaTeX。关闭可提速 |
| `enable_table` | `bool` | 否 | `true` | `true` / `false` | 是否识别表格并转 HTML。关闭可提速 30-50% |
| `language` | `string` | 否 | `"ch"` | `"ch"` / `"en"` / `"ja"` | 文档主体语言 |
| `model_version` | `string` | 否 | `"pipeline"` | `"pipeline"` / `"vlm"` / `"MinerU-HTML"` | 解析引擎。`vlm` 精度更高但更慢 |
| `page_ranges` | `string` | 否 | — | `"2,4-6"` / `"1--2"` | 指定解析页码范围 |
| `extra_formats` | `[string]` | 否 | — | `"docx"` / `"html"` / `"latex"` | 额外导出格式 |
| `callback` | `string` | 否 | — | HTTP/HTTPS URL | 回调地址。设置后无需轮询 |
| `seed` | `string` | 条件必传 | — | 任意字符串 | 回调签名密钥。`callback` 设置时必传 |
| `no_cache` | `bool` | 否 | `false` | `true` / `false` | 是否绕过缓存 |
| `cache_tolerance` | `int` | 否 | `900` | 秒 | 缓存容忍时间 |

### 4.2 认证头

| Header | 值 | 必传 |
|---|---|---|
| `Content-Type` | `application/json` | ✅ |
| `Authorization` | `Bearer {token}` | ✅ |

### 4.3 任务状态机

```
pending → running → converting → done
                       ↘ failed (err_msg)
```

| state | 含义 |
|---|---|
| `pending` | 排队中 |
| `running` | 解析中 (含 `extract_progress`) |
| `converting` | 格式转换中 |
| `done` | 完成 (含 `full_zip_url`) |
| `failed` | 失败 (含 `err_msg`) |

### 4.4 BridgePipeline 中 MinerU 相关 .env 配置

```bash
MINERU_API_TOKEN=<jwt-token>
MINERU_API_BASE_URL=https://mineru.net/api/v4/extract/task
MINERU_LANGUAGE=en
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_MODEL_VERSION=pipeline
MINERU_MAX_WAIT_SECONDS=600
MINERU_POLL_INTERVAL=5
```

---

## 5. LangExtract 关键参数规范

### 5.1 lx.extract() 主参数

| 参数 | 类型 | 必传 | 默认值 | 说明 |
|---|---|---|---|---|
| **`text_or_documents`** | `str \| Iterable[Document]` | **✅** | — | 输入文本或文档列表 |
| **`examples`** | `Sequence[ExampleData]` | **✅** | — | Few-shot 示例 (**空则报错**) |
| `prompt_description` | `str \| None` | 否 | — | 抽取任务指令 |
| `config` | `ModelConfig \| None` | 否 | — | **优先级高于 model_id** |
| `model_id` | `str` | 否 | `"gemini-3.5-flash"` | 模型 ID |
| `temperature` | `float \| None` | 否 | `None` | `0.0` = 确定性输出 |
| `max_char_buffer` | `int` | 否 | `1000` | 分块最大字符数。学术论文建议 `3000` |
| `context_window_chars` | `int \| None` | 否 | `None` | 跨块上下文窗口。建议 `200` |
| `batch_length` | `int` | 否 | `10` | 每批处理块数 |
| `max_workers` | `int` | 否 | `10` | 最大并行数 |
| `extraction_passes` | `int` | 否 | `1` | 多轮抽取次数。**每轮 x N 倍 token 消耗** |
| `use_schema_constraints` | `bool` | 否 | `True` | **DeepSeek 必须 False** |
| `fence_output` | `bool \| None` | 否 | `None` | **DeepSeek 必须 True** |
| `show_progress` | `bool` | 否 | `True` | 进度条 |
| `debug` | `bool` | 否 | `False` | 调试日志 |
| `prompt_validation_level` | `PromptValidationLevel` | 否 | `WARNING` | `WARNING`=告警继续 / `ERROR`=中断 / `OFF`=跳过 |

### 5.2 ModelConfig 参数

| 字段 | 类型 | 必传 | 说明 |
|---|---|---|---|
| `model_id` | `str \| None` | 否 | 模型标识 |
| `provider` | `str \| None` | 否 | `"openai"` / `"gemini"` / `"ollama"` |
| `provider_kwargs` | `dict` | 否 | `api_key`, `base_url`, `temperature` |

### 5.3 Provider 兼容性矩阵

| 能力 | Gemini | OpenAI (GPT) | DeepSeek (OpenAI Compat) |
|---|---|---|---|
| `use_schema_constraints` | `True` (JSON Schema) | `True` (JSON mode) | **`False`** |
| `fence_output` | `False` (raw JSON) | auto | **`True`** |
| `base_url` 自定义 | 不支持 | 支持 | 支持 (`https://api.deepseek.com`) |

### 5.4 BridgePipeline 中 LangExtract 相关 .env 配置

```bash
LANGEXTRACT_API_KEY=sk-xxx
LANGEXTRACT_MODEL_ID=deepseek-chat
LANGEXTRACT_BASE_URL=https://api.deepseek.com
LANGEXTRACT_TEMPERATURE=0.0
LANGEXTRACT_MAX_CHAR_BUFFER=3000
LANGEXTRACT_CONTEXT_WINDOW_CHARS=200
LANGEXTRACT_EXTRACTION_PASSES=1
```

---

## 6. 组件接口对接规范

### 6.1 数据流转图

```
MinerU Output                    BridgePipeline              LangExtract Input
─────────────────────────────────────────────────────────────────────────────────

full.md ───────────────────────→ Section Splitter ────────→ Document.text
  (Markdown, ~42KB)                ↓                          (str, ~200-8000 chars)
                                list[SectionSplit]
                                      │
content_list.json ─────────────→ PositionMap ──────────────→ document_id
  [{type,text,bbox,                 ↓                          (str, "sec_N_title")
    text_level,page_idx},...]   Segment[]
                                      │
layout.json ───────────────────→ (reserved)                → additional_context
  {pdf_info:...}                                             (str, "Section: {title}")
```

### 6.2 数据格式转换规范

#### 6.2.1 MinerU content_list → PositionMap

**输入**: `content_list.json` (JSON array, 141 items)
**输出**: `PositionMap` (134 segments)

**转换规则**:
1. 遍历 content_list 的每个 item
2. 调用 `_item_to_text()` 提取可显示文本:
   - `text` → `item.text`
   - `table` → `" ".join(item.table_caption)`
   - `equation` → `item.text`
   - `image` → `" ".join(item.image_caption)` 或 `"[Image]"`
   - `chart` → `" ".join(item.chart_caption)` 或 `"[Chart]"`
   - `page_number` → 空字符串 (跳过)
3. 对文本做 whitespace 归一化 (`re.sub(r"\s+", " ", text).strip()`)
4. 在 `full.md` 中搜索归一化文本位置
5. 记录 `(char_start, char_end)` → `(source_item_idx, page_idx, bbox, block_type, text_level)`

#### 6.2.2 SectionSplit → LangExtract Document

**输入**: `list[SectionSplit]` + `full.md`
**输出**: `list[langextract.core.data.Document]`

**转换规则**:
1. `full.md[section.char_start:section.char_end].strip()` → `Document.text`
2. `section.document_id` → `Document.document_id` (如 `"sec_6_3_1_encoder_and_decoder_stacks"`)
3. `f"Section: {section.title}"` → `Document.additional_context`
4. 长度 < 10 chars 的空段落跳过
5. `< 150 chars` 的短 section 合并到前一 section

#### 6.2.3 LangExtract Extraction → GroundedExtraction

**输入**: `Extraction` (from `AnnotatedDocument.extractions`)
**输出**: `GroundedExtraction`

**转换规则**:
1. `ext.char_interval.start_pos + document_offsets[doc_id]` → `global_start`
2. `ext.char_interval.end_pos + document_offsets[doc_id]` → `global_end`
3. `position_map.lookup_range(global_start, global_end)` → `Segment`
4. `Segment.page_idx` → `GroundedExtraction.page_idx`
5. `Segment.bbox` → `GroundedExtraction.bbox_norm`
6. `Segment.block_type` → `GroundedExtraction.block_type`
7. `None` char_interval → `grounding_status: "ungrounded"`

### 6.3 传输方式

| 阶段 | 传输方式 | 说明 |
|---|---|---|
| MinerU → Bridge | 文件系统 (JSON) | ZIP 解压后本地文件 |
| Bridge → LangExtract | Python 内存对象 | `list[Document]` 直接传入 |
| LangExtract → Grounding | Python 内存对象 | `list[AnnotatedDocument]` |
| Grounding → KG | Python 内存对象 | `list[GroundedExtraction]` |
| KG → 持久化 | 文件系统 (JSON) | `nodes.json` + `edges.json` |

### 6.4 衔接逻辑

```
Stage 1 ──(文件路径)──→ Stage 2 ──(list[Document]+PositionMap)──→ Stage 3
                            │
                            ├─ documents → lx.extract(text_or_documents=documents, ...)
                            └─ offsets → 保存到 dict[document_id → global_char_pos]

Stage 3 ──(list[AnnotatedDocument])──→ Stage 4
                            │
                            └─ grounding.resolve_grounding(annotated, position_map, offsets)

Stage 4 ──(list[GroundedExtraction])──→ Stage 5
                            │
                            └─ kg_builder.build_knowledge_graph(grounded)
                                   └─ → nodes.json + edges.json
```

---

## 7. BridgePipeline 输出参数规范

### 7.1 最终输出文件

| 文件 | 格式 | 大小 (实测) | 说明 |
|---|---|---|---|
| `nodes.json` | JSON | ~119 KB (310 nodes) | KG 节点，GraphRAG 的 vertex set |
| `edges.json` | JSON | ~360 KB (1,529 edges) | KG 边，GraphRAG 的 edge set |
| `integrated_*.jsonl` | JSONL | 可变 | Stage 3 中间输出，含原始 entity 列表 |

### 7.2 nodes.json 完整参数

| 字段 | 类型 | 含义 | 使用场景 |
|---|---|---|---|
| `metadata.pipeline` | `string` | Pipeline 标识 | 溯源 |
| `metadata.model` | `string` | LLM 模型 | 溯源 |
| `metadata.timestamp` | `string` (ISO 8601) | 生成时间 | 版本管理 |
| `node_count` | `int` | 节点总数 | 统计 |
| `nodes[].node_id` | `string` | 唯一 ID | GraphRAG 索引键 |
| `nodes[].entity_type` | `string` | 实体类别 | 节点分类/查询过滤 |
| `nodes[].label` | `string` | 实体文本 | 检索显示 |
| `nodes[].properties` | `dict` | 实体属性 | 实体详情/过滤 |
| `nodes[].page_idx` | `int \| null` | PDF 页码 (0-based) | 溯源定位到原始文档页码 |
| `nodes[].bbox_norm` | `[x0,y0,x1,y1] \| null` | 0-1000 归一化包围框 | 溯源高亮原始文档区域 |
| `nodes[].grounding_status` | `"grounded" \| "ungrounded"` | 接地状态 | 可靠度筛选 (graphrag 建议只使用 grounded) |

### 7.3 edges.json 完整参数

| 字段 | 类型 | 含义 | 使用场景 |
|---|---|---|---|
| `edge_count` | `int` | 边总数 | 统计 |
| `edges[].edge_id` | `string` | 唯一 ID | GraphRAG 索引键 |
| `edges[].source_node_id` | `string` | 源节点 ID | 图谱边起点 |
| `edges[].target_node_id` | `string` | 目标节点 ID | 图谱边终点 |
| `edges[].relation_type` | `string` | 关系类型 (`co_occurs_with`/`same_type`/`adjacent_to`) | 遍历策略 / 权重分配 |
| `edges[].properties.rule` | `string` | 生成规则 | 边置信度判断 |

### 7.4 entity_type 完整枚举

| entity_type | 含义 | 典型 attributes |
|---|---|---|
| `paper_metadata` | 论文元信息 | `field: "title"/"author"/"affiliation"/"venue"/"date"` |
| `section_header` | 章节标题 | `level: 1-6` |
| `model_component` | 模型组件 | `component_type: "layer"/"mechanism"/"module"/"function"`, `parameter: str` |
| `metric` | 数值指标 | `name: str`, `value: str`, `unit: str`, `task: str` |
| `dataset` | 数据集 | `name: str`, `version: str`, `task: str`, `language_pair: str` |
| `method` | 方法/技术 | `category: "training"/"optimization"/"regularization"`, `parameter: str` |
| `definition` | 概念定义 | `concept: str` |
| `equation` | 公式 | `name: str`, `latex: str` |
| `reference` | 引用 | `citation_key: str`, `authors: str` |
| `claim` | 论断/结论 | `claim_type: "observation"/"conclusion"`, `confidence: str` |

### 7.5 .env 配置完整清单

```bash
# ============ MinerU ============
MINERU_API_TOKEN=<jwt-token>                    # JWT Token (mineru.net 申请)
MINERU_API_BASE_URL=https://mineru.net/api/v4/extract/task
MINERU_LANGUAGE=en                              # ch/en/ja
MINERU_ENABLE_FORMULA=true
MINERU_ENABLE_TABLE=true
MINERU_MODEL_VERSION=pipeline                   # pipeline/vlm
MINERU_MAX_WAIT_SECONDS=600                     # 最大轮询时间
MINERU_POLL_INTERVAL=5                          # 轮询间隔 (秒)

# ============ 文件来源 ============
LOCAL_PDF_PATH=./input/sample.pdf               # 本地 PDF 路径
FILE_URL=                                       # 公网 URL (优先)

# ============ LangExtract / DeepSeek ============
LANGEXTRACT_API_KEY=sk-xxx                      # DeepSeek API Key
LANGEXTRACT_MODEL_ID=deepseek-chat              # deepseek-chat / deepseek-reasoner
LANGEXTRACT_BASE_URL=https://api.deepseek.com
LANGEXTRACT_TEMPERATURE=0.0
LANGEXTRACT_MAX_CHAR_BUFFER=3000                # 每 chunk 最大字符
LANGEXTRACT_CONTEXT_WINDOW_CHARS=200            # 跨块上下文
LANGEXTRACT_EXTRACTION_PASSES=1

# ============ 分段策略 ============
CHUNK_STRATEGY=section                          # section/page/full_document
SECTION_MIN_LEVEL=2                             # 最小标题层级 (1=H1, 2=H2)
MIN_SECTION_CHARS=150                           # 短 section 合并阈值

# ============ 输出 ============
OUTPUT_DIR=./output/kg
EXAMPLES_PATH=./config/extraction_examples.yaml
```

---

## 8. 运行环境与 CLAUDE.md

### 8.1 虚拟环境要求

BridgePipeline 与 LangExtract **共用同一虚拟环境** (MinerU 通过 curl 子进程调用，无需其 venv)。

**启动前必须执行**:

```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
```

验证环境:

```bash
python -c "import sys; print(sys.prefix)"
# 输出: D:\graghRAG-agent\langextract\.venv
```

### 8.2 虚拟环境架构

```
D:\graghRAG-agent\
├── integration\              ← BridgePipeline (共用 langextract .venv)
│   └── pipeline.py
├── langextract\              ← LangExtract
│   └── .venv\                ← 63 个包, Python 3.12.8 (← BridgePipeline 使用此环境)
├── mineru-mvp-test\          ← MinerU MVP
│   └── .venv\                ← 10 个包, Python 3.12.8
└── docs\                     ← 所有规范文档
```

### 8.3 CLAUDE.md

**位置**: `D:\graghRAG-agent\integration\CLAUDE.md`

```markdown
# BridgePipeline — CLAUDE.md

## 项目概述

BridgePipeline 是 MinerU → LangExtract 的组件对接管道，
负责将 MinerU 文档解析结果转换为 LangExtract 结构化抽取输入，
并最终生成 Knowledge Graph 的 nodes.json 和 edges.json，
作为 GraphRAG 索引阶段的核心流程。

## 必读：虚拟环境

BridgePipeline 与 LangExtract 共用虚拟环境。
所有 python 命令启动前必须先激活:

    source D:/graghRAG-agent/langextract/.venv/Scripts/activate

首次创建 Langextract 环境:

    cd D:/graghRAG-agent/langextract
    uv venv .venv --python 3.12
    source .venv/Scripts/activate
    uv pip install -e ".[test]"

## 运行方式

    cd D:/graghRAG-agent/integration
    python pipeline.py --cached ../mineru-mvp-test/output/87bc1f56
    python pipeline.py --pdf ../mineru-mvp-test/sample.pdf

## 环境约束

1. 启动前必须激活 langextract .venv
2. .env 中的 API Key 和 Token 为敏感信息，不提交 git
3. 依赖变更: uv pip install -r requirements.txt
4. Python >= 3.10 (环境使用 3.12)
```

---

## 环境变量与凭证（来自 OSS 排障报告回流，2026-05-29）

### 必需环境变量清单

| 变量名 | 用途 | 校验时机 |
|--------|------|---------|
| `OSS_ACCESS_KEY_ID` | 阿里云 OSS 访问 ID | 进程启动时 |
| `OSS_ACCESS_KEY_SECRET` | 阿里云 OSS 访问密钥 | 进程启动时 |
| `OSS_BUCKET` | OSS Bucket 名 | 进程启动时 |
| `OSS_ENDPOINT` | OSS endpoint（如 `oss-cn-shanghai.aliyuncs.com`） | 进程启动时 |
| `MINERU_API_KEY` | MinerU 云端 API Key | 调用 MinerU 前 |
| `DEEPSEEK_API_KEY` | DeepSeek 用于 LangExtract | 调用 LangExtract 前 |

### 凭证校验铁律

1. **启动时校验，不要运行时校验**：进程启动后立即检查上述变量全部非空，缺一项 fail-fast 退出
2. **永远不要把 Key 写进日志**：禁止 `logger.info(f"oss key = {key}")` 这类语句；如需调试只能打印 `key[:4] + "***"`
3. **永远不要写入持久化存储**：禁止把 Key 写进 SQLite / Neo4j / 输出文件
4. `.env` 必须在 `.gitignore`；新建凭证时同步更新 `.env.example`（用占位符值）

### 常见错误与定位

- `AccessKeyId not found` → 检查 `load_dotenv()` 是否在所有 import 之前
- `SignatureDoesNotMatch` → AccessKeyId 与 Secret 不匹配，重新核对
- `NoSuchBucket` → `OSS_BUCKET` 拼写或大小写错误
- `RequestTimeout` → endpoint 区域错配，检查 `OSS_ENDPOINT` 是否与 Bucket 所在区域一致
