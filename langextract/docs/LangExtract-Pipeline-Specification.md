# LangExtract Pipeline 规范文档

> **版本**: v1.0 | **日期**: 2026-05-24 | **状态**: ✅ 已通过 DeepSeek MVP 实测验证
>
> 基于 `google/langextract` v1.5.0 源码 + DeepSeek (via OpenAI Provider) 实测结果。

---

## 目录

1. [核心 Pipeline 输入规范](#1-核心-pipeline-输入规范)
2. [文本模型接入规范](#2-文本模型接入规范)
3. [Pipeline 输出数据格式规范](#3-pipeline-输出数据格式规范)
4. [Pipeline 执行流程](#4-pipeline-执行流程)
5. [关键参数规范详解](#5-关键参数规范详解)
6. [本地实测输出文件清单](#6-本地实测输出文件清单)
7. [运行环境准备](#7-运行环境准备)
8. [实测附录：DeepSeek MVP 验证](#8-实测附录deepseek-mvp-验证)

---

## 1. 核心 Pipeline 输入规范

### 1.1 主入口函数签名

唯一公共入口 `lx.extract()`，定义在 `langextract/extraction.py:36-65`：

```python
def extract(
    text_or_documents: str | Iterable[data.Document],
    prompt_description: str | None = None,
    examples: typing.Sequence[typing.Any] | None = None,
    model_id: str = "gemini-3.5-flash",
    config: ModelConfig | None = None,
    # ... 其他可选参数
) -> list[data.AnnotatedDocument] | data.AnnotatedDocument:
```

### 1.2 支持的输入类型

| 类型 | Python 类型 | 返回值类型 | 说明 |
|---|---|---|---|
| **纯文本字符串** | `str` | `AnnotatedDocument` | 直接传入文本内容 |
| **Document 对象** | `langextract.core.data.Document` | `AnnotatedDocument` | 可指定 `document_id` 和 `additional_context` |
| **Document 列表** | `Iterable[Document]` | `list[AnnotatedDocument]` | 批量并行处理 |
| **CSV 数据集** | `langextract.io.Dataset` | `Iterator[Document]` | 从 CSV 文件加载 text 列 |
| **HTTP/HTTPS URL** | `str` (需 `fetch_urls=True`) | `AnnotatedDocument` | 下载纯文本内容 |

#### Document 数据结构 (`core/data.py:130-156`)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | `str` | ✅ 是 | 待抽取的原始纯文本 |
| `document_id` | `str \| None` | 否 | 唯一标识，未提供时自动生成 `doc_{uuid[:8]}` |
| `additional_context` | `str \| None` | 否 | 注入到每条 prompt 的额外上下文 |

### 1.3 ExampleData 结构 (`core/data.py:260-270`)

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | `str` | ✅ 是 | 示例原文 |
| `extractions` | `list[Extraction]` | ✅ 是 | 对应的抽取结果列表 |

每项 `Extraction` 包含:

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `extraction_class` | `str` | ✅ 是 | 实体类别标签 |
| `extraction_text` | `str` | ✅ 是 | 从原文中**精确复制**的实体文本 |
| `attributes` | `dict[str, str\|list[str]] \| None` | 否 | 实体属性键值对 |
| `char_interval` | `CharInterval \| None` | 否 | 字符区间，自动对齐后填充 |
| `description` | `str \| None` | 否 | 实体描述 |

> **注意**: `extraction_text` 必须为示例 `text` 中的 verbatim 子串，否则触发 `WARNING` 级别的 Prompt alignment 校验告警。

---

## 2. 文本模型接入规范

### 2.1 模型类型：仅文本模型

`BaseLanguageModel.infer()` (`core/base_model.py:122`) 输入为 `batch_prompts: Sequence[str]`，仅接收文本字符串。不接收图像、音频等模态。

### 2.2 内置支持的 Provider

| Provider | 模块 | 模型 ID 示例 |
|---|---|---|
| Google Gemini | `langextract.providers.gemini` | `gemini-3.5-flash`, `gemini-2.5-pro` |
| OpenAI | `langextract.providers.openai` | `gpt-4o`, `gpt-4o-mini` |
| Ollama | `langextract.providers.ollama` | `gemma2:2b`, `llama3` |

### 2.3 模型接入方式

#### 方式一：简单模式

```python
result = lx.extract(
    text_or_documents=text,
    prompt_description=prompt,
    examples=examples,
    model_id="gemini-3.5-flash",
)
```

#### 方式二：ModelConfig 显式配置 (实测验证)

```python
from langextract.factory import ModelConfig

config = ModelConfig(
    model_id="deepseek-chat",        # 模型标识
    provider="openai",               # Provider 名称
    provider_kwargs={
        "api_key": "sk-xxx",
        "base_url": "https://api.deepseek.com",  # 自定义端点
    },
)
result = lx.extract(..., config=config)
```

#### 方式三：自定义 Provider 插件

通过 `@router.register(...)` 注册，支持自定义推理逻辑。详见 `langextract/providers/README.md`。

### 2.4 第三方 Provider 接入实测：DeepSeek

**配置参数**:

| 参数 | 值 |
|---|---|
| `provider` | `"openai"` |
| `model_id` | `"deepseek-chat"` |
| `base_url` | `https://api.deepseek.com` |
| `api_key` | DeepSeek API Key |

**兼容性说明**:

| DeepSeek 支持 | 状态 |
|---|---|
| `response_format` JSON mode | ❌ 不支持 (`This response_format type is unavailable now`) |
| YAML + fence 模式 | ✅ 可用 |

**DeepSeek 适配配置**:

```python
use_schema_constraints = False   # 必须关闭 JSON Schema 约束
fence_output = True              # 启用 ```yaml fence 输出
```

### 2.5 API Key 配置方式

| 方式 | 说明 |
|---|---|
| 环境变量 | `LANGEXTRACT_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` |
| `.env` 文件 | `python-dotenv` 自动加载 |
| `ModelConfig.provider_kwargs["api_key"]` | 代码直接传入 (测试用) |

---

## 3. Pipeline 输出数据格式规范

### 3.1 AnnotatedDocument (内存对象)

```python
@dataclasses.dataclass
class AnnotatedDocument:
    extractions: list[Extraction] | None   # 抽取实体列表
    text: str | None                        # 原始文档文本
    document_id: str                        # 文档唯一标识
```

### 3.2 Extraction 实体数据结构

| 字段 | 类型 | 说明 |
|---|---|---|
| `extraction_class` | `str` | 实体类别 |
| `extraction_text` | `str` | 实体原文文本 |
| `char_interval` | `CharInterval \| None` | 字符区间。`None` = 未接地 (LLM 幻觉) |
| `alignment_status` | `AlignmentStatus \| None` | 对齐状态枚举 |
| `attributes` | `dict \| None` | 属性键值对 |
| `extraction_index` | `int \| None` | 批次内序号 |
| `group_index` | `int \| None` | 分组索引 |
| `description` | `str \| None` | 描述 |

**AlignmentStatus 枚举值**:

| 值 | 含义 |
|---|---|
| `match_exact` | 精确匹配 |
| `match_fuzzy` | 模糊匹配 |
| `match_lesser` | 部分匹配 |
| `match_greater` | 扩展匹配 |

### 3.3 JSONL 持久化格式

```json
{
    "document_id": "doc_2140538c",
    "text": "患者张三，男，45岁...",
    "extractions": [
        {
            "extraction_class": "demographic",
            "extraction_text": "男",
            "char_interval": {"start_pos": 5, "end_pos": 6},
            "alignment_status": "match_exact",
            "extraction_index": 1,
            "group_index": 0,
            "description": null,
            "attributes": {"gender": "male", "age": "45岁"}
        },
        {
            "extraction_class": "measurement",
            "extraction_text": "BP 145/90mmHg",
            "char_interval": {"start_pos": 203, "end_pos": 216},
            "alignment_status": "match_exact",
            "extraction_index": 14,
            "group_index": 13,
            "description": null,
            "attributes": {
                "type": "blood_pressure",
                "systolic": "145",
                "diastolic": "90",
                "unit": "mmHg"
            }
        }
    ]
}
```

> 以上 JSON 示例截取自 2026-05-24 DeepSeek MVP 实测输出。

### 3.4 JSONL 输出字段规范

| JSON Key | 类型 | 来源 |
|---|---|---|
| `document_id` | `str` | `AnnotatedDocument.document_id` |
| `text` | `str \| null` | `AnnotatedDocument.text` |
| `extractions` | `list[dict]` | `AnnotatedDocument.extractions` |
| `extractions[n].extraction_class` | `str` | `Extraction.extraction_class` |
| `extractions[n].extraction_text` | `str` | `Extraction.extraction_text` |
| `extractions[n].char_interval` | `dict \| null` | `Extraction.char_interval`, `null` = 未接地 |
| `extractions[n].char_interval.start_pos` | `int` | `CharInterval.start_pos` (inclusive) |
| `extractions[n].char_interval.end_pos` | `int` | `CharInterval.end_pos` (exclusive) |
| `extractions[n].alignment_status` | `str \| null` | `AlignmentStatus.value` |
| `extractions[n].extraction_index` | `int \| null` | `Extraction.extraction_index` |
| `extractions[n].group_index` | `int \| null` | `Extraction.group_index` |
| `extractions[n].description` | `str \| null` | `Extraction.description` |
| `extractions[n].attributes` | `dict \| null` | `Extraction.attributes` |

**序列化规则** (`data_lib.py:27-54`):
- 私有字段 (`_` 前缀) 不输出
- Enum 序列化为 `.value` 字符串
- 数值类型统一转为 Python `int`

### 3.5 有效实体过滤

```python
grounded = [e for e in result.extractions if e.char_interval is not None]
```

`char_interval = None` 表示 LLM 返回的实体无法在原文中定位（幻觉或 Few-shot 迁移），应在下游使用时过滤。

---

## 4. Pipeline 执行流程

### 4.1 完整执行链路

```
┌──────────────────────────────────────────────────────────────────┐
│                  LangExtract Pipeline 完整流程                     │
│                                                                  │
│  [1] 环境准备                                                    │
│      ├─ source .venv/Scripts/activate   (进入虚拟环境)            │
│      ├─ 配置 API Key (.env 或 代码传入)                           │
│      └─ 安装 openai 扩展: uv pip install "openai>=1.50.0"        │
│                           ↓                                      │
│  [2] 构造输入数据                                                │
│      ├─ 构造纯文本 str (临床/法律/学术文本)                        │
│      ├─ 定义 prompt_description (抽取指令)                        │
│      └─ 构建 examples (Few-shot 示例, 每个示例 ≤ 6 个实体)        │
│                           ↓                                      │
│  [3] 配置 ModelConfig                                            │
│      ├─ model_id + provider + provider_kwargs                     │
│      └─ DeepSeek: use_schema_constraints=False, fence_output=True │
│                           ↓                                      │
│  [4] 调用 lx.extract()                                           │
│      ├─ Prompt 验证 (PromptAlignment: WARNING→继续 / ERROR→中断)  │
│      ├─ 文本分块 (ChunkIterator: max_char_buffer 控制)            │
│      ├─ LLM 推理 (BaseLanguageModel.infer)                        │
│      ├─ 输出解析 (Resolver: YAML/JSON → Extraction 对象)          │
│      └─ 实体对齐 (Resolver.align: LCS 字符串匹配 → char_interval) │
│                           ↓                                      │
│  [5] 接收 AnnotatedDocument                                      │
│      ├─ 过滤接地实体: [e for e in result.extractions if e.char_interval] │
│      └─ 按类别统计: collections.Counter(e.extraction_class)       │
│                           ↓                                      │
│  [6] 持久化输出                                                  │
│      ├─ JSONL: lx.io.save_annotated_documents([result], ...)      │
│      └─ 结构化摘要 JSON: 自定义 json.dump                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 测试脚本存放路径

| 文件 | 路径 | 说明 |
|---|---|---|
| **MVP 测试脚本** | `D:\graghRAG-agent\langextract\mvp_deepseek_test.py` | DeepSeek 接入验证 |
| **规范文档** | `D:\graghRAG-agent\langextract\docs\LangExtract-Pipeline-Specification.md` | 本文档 |
| **CLAUDE.md** | `D:\graghRAG-agent\langextract\CLAUDE.md` | 项目规范 (含环境激活) |
| **输出目录** | `D:\graghRAG-agent\langextract\output\` | 所有测试输出 |
| **核心源码** | `D:\graghRAG-agent\langextract\langextract\` | 库代码 |

### 4.3 测试脚本核心逻辑

`mvp_deepseek_test.py` 的 6 个阶段:

| 阶段 | 代码行 | 职责 |
|---|---|---|
| ① DeepSeek 配置 | L23-30 | ModelConfig(model_id, provider, provider_kwargs) |
| ② 模拟文本 | L36-55 | 517 chars 中文临床文本 |
| ③ Few-shot 示例 | L73-112 | 1 个 ExampleData, 6 个 Extraction |
| ④ 执行抽取 | L130-143 | lx.extract() + DeepSeek 适配参数 |
| ⑤ 结果分析 | L152-186 | 接地/未接地过滤 + 按类别统计 |
| ⑥ 持久化输出 | L191-231 | JSONL + 结构化摘要 JSON |

---

## 5. 关键参数规范详解

### 5.1 lx.extract() 完整参数表

| 参数 | 类型 | 必传 | 默认值 | 说明 |
|---|---|---|---|---|
| `text_or_documents` | `str \| Iterable[Document]` | ✅ 是 | — | 输入文本或文档 |
| `prompt_description` | `str \| None` | 否 | — | 抽取任务指令 |
| `examples` | `Sequence[ExampleData] \| None` | ✅ 是 | — | Few-shot 示例 (空则报错) |
| `model_id` | `str` | 否 | `"gemini-3.5-flash"` | 模型标识 |
| `config` | `ModelConfig \| None` | 否 | — | 模型配置 (优先级高于 model_id) |
| `api_key` | `str \| None` | 否 | — | API Key |
| `temperature` | `float \| None` | 否 | `None` (模型默认) | 采样温度, `0.0` = 确定性 |
| `max_char_buffer` | `int` | 否 | `1000` | 分块最大字符数 |
| `batch_length` | `int` | 否 | `10` | 每批处理块数 |
| `max_workers` | `int` | 否 | `10` | 最大并行数 |
| `use_schema_constraints` | `bool` | 否 | `True` | **DeepSeek 须设为 False** |
| `fence_output` | `bool \| None` | 否 | `None` (自动) | **DeepSeek 须设为 True** |
| `extraction_passes` | `int` | 否 | `1` | 多轮抽取次数 (提高召回率) |
| `context_window_chars` | `int \| None` | 否 | `None` | 跨块上下文窗口 |
| `show_progress` | `bool` | 否 | `True` | 进度条 |
| `debug` | `bool` | 否 | `False` | 调试日志 |
| `prompt_validation_level` | `PromptValidationLevel` | 否 | `WARNING` | 示例对齐校验级别 |

### 5.2 ModelConfig 参数

| 字段 | 类型 | 必传 | 说明 |
|---|---|---|---|
| `model_id` | `str \| None` | 否 | 模型 ID，与 provider 至少提供一个 |
| `provider` | `str \| None` | 否 | Provider 名称 ("openai"/"gemini"/"ollama") |
| `provider_kwargs` | `dict` | 否 | Provider 特定参数 |

**provider_kwargs 常用键**:

| 键 | 类型 | 说明 |
|---|---|---|
| `api_key` | `str` | API Key |
| `base_url` | `str` | 自定义 API 端点 (DeepSeek: `https://api.deepseek.com`) |
| `temperature` | `float` | 采样温度 |
| `max_workers` | `int` | 最大并发 |

### 5.3 第三方 Provider 兼容性矩阵

| 参数 | Gemini | OpenAI (GPT) | DeepSeek (OpenAI Compat) |
|---|---|---|---|
| `use_schema_constraints` | `True` (原生 JSON Schema) | `True` (JSON mode) | **`False`** |
| `fence_output` | `False` (raw JSON) | `auto` | **`True`** |
| `schema` 应用 | 自动 | 自动 | 不可用 |
| `response_format` | `response_mime_type` | `response_format={"type": "json_object"}` | 不兼容 |

### 5.4 DeepSeek 接入必读

```python
# ✅ 正确配置
config = ModelConfig(
    model_id="deepseek-chat",
    provider="openai",
    provider_kwargs={
        "api_key": "sk-xxx",
        "base_url": "https://api.deepseek.com",
    },
)

result = lx.extract(
    ...,
    config=config,
    use_schema_constraints=False,   # DeepSeek 不支持 JSON mode
    fence_output=True,              # 降级为 YAML fence 解析
)
```

---

## 6. 本地实测输出文件清单

### 6.1 实测文件 (2026-05-24, deepseek-v4-pro)

| 文件名 | 大小 | 格式 | 说明 |
|---|---|---|---|
| `deepseek_mvp_20260524_160948.jsonl` | 8.8 KB | JSONL | 行式 JSON, 每行一个 AnnotatedDocument |
| `deepseek_mvp_20260524_160948_summary.json` | 5.2 KB | JSON | 结构化摘要 (统计 + 全量实体列表) |

### 6.2 Summary JSON 结构

```json
{
    "model": "deepseek-chat (via OpenAI Provider)",
    "input_chars": 517,
    "total_extractions": 27,
    "grounded": 21,
    "ungrounded": 6,
    "class_counts": {
        "demographic": 1,
        "condition": 8,
        "measurement": 8,
        "medication": 4
    },
    "extractions": [
        {
            "class": "measurement",
            "text": "BP 145/90mmHg",
            "attributes": {
                "type": "blood_pressure",
                "systolic": "145",
                "diastolic": "90",
                "unit": "mmHg"
            },
            "char_interval": [203, 216]
        }
    ]
}
```

### 6.3 JSONL 文件加载

```python
from langextract import io
import pathlib

docs = list(io.load_annotated_documents_jsonl(
    pathlib.Path("output/deepseek_mvp_20260524_160948.jsonl")
))
for doc in docs:
    for ext in doc.extractions:
        if ext.char_interval:
            print(f"[{ext.extraction_class}] {ext.extraction_text}")
```

### 6.4 可视化输出

```python
html = lx.visualize("output/deepseek_mvp_20260524_160948.jsonl")
with open("visualization.html", "w", encoding="utf-8") as f:
    f.write(html if isinstance(html, str) else html.data)
```

---

## 7. 运行环境准备

### 7.1 虚拟环境 (强制)

LangExtract 使用 `uv` 管理独立 Python 虚拟环境，与 MinerU 组件完全隔离。

**启动前必须执行**:

```bash
source D:/graghRAG-agent/langextract/.venv/Scripts/activate
```

验证:

```bash
python -c "import sys; print(sys.prefix)"
# 预期: D:\graghRAG-agent\langextract\.venv
```

> 详见 `D:\graghRAG-agent\langextract\CLAUDE.md`

### 7.2 首次环境创建

```bash
cd D:/graghRAG-agent/langextract
uv venv .venv --python 3.12
source .venv/Scripts/activate
uv pip install -e ".[test]"
```

### 7.3 环境隔离架构

```
D:\graghRAG-agent\
├── langextract\          ← 63 个包 (google-genai, pandas, numpy, pytest...)
│   └── .venv\            ← 155 MB, Python 3.12.8
│
└── mineru-mvp-test\      ← 10 个包 (requests, fpdf2, python-dotenv)
    └── .venv\            ← 30 MB, Python 3.12.8
```

### 7.4 环境依赖

| 包名 | 版本 |
|---|---|
| `langextract` | 1.5.0 (开发模式) |
| `google-genai` | 2.6.0 |
| `openai` | 2.38.0 |
| `pandas` | 3.0.3 |
| `numpy` | 2.4.6 |
| `pydantic` | 2.13.4 |
| `google-cloud-storage` | 3.10.1 |
| `pytest` | 9.0.3 |

---

## 8. 实测附录：DeepSeek MVP 验证

### 8.1 测试配置

| 项目 | 值 |
|---|---|
| Provider | OpenAI Compat |
| Base URL | `https://api.deepseek.com` |
| Model | `deepseek-v4-pro` |
| 输入 | 中文临床病历文本 (517 chars) |
| Few-shot 示例 | 1 个, 6 个 Extraction |
| `use_schema_constraints` | `False` |
| `fence_output` | `True` |
| `temperature` | `0.0` |

### 8.2 测试结果

| 指标 | 数值 |
|---|---|
| 总抽取数 | 27 |
| 已接地 | 21 (77.8%) |
| 未接地 | 6 (22.2%) |
| 耗时 | ~1m47s |
| 类别数 | 4 (condition, measurement, medication, demographic) |

### 8.3 按类别统计

| 类别 | 数量 | 示例实体 |
|---|---|---|
| `condition` | 8 | 冠状动脉粥样硬化性心脏病, 高血压病2级, 2型糖尿病, ST-T改变 |
| `measurement` | 8 | T 36.5°C, P 88次/分, BP 145/90mmHg, LVEF 55% |
| `medication` | 4 | 硝苯地平控释片30mg qd, 二甲双胍0.5g tid, 阿托伐他汀钙片20mg qn, 美托洛尔缓释片47.5mg qd |
| `demographic` | 1 | 男 (45岁) |

### 8.4 与 deepseek-chat (V3.2) 对比

| 指标 | deepseek-chat | deepseek-v4-pro |
|---|---|---|
| 总抽取 | 30 | 27 |
| 已接地 | 23 (76.7%) | 21 (77.8%) |
| condition | 10 | 8 |
| measurement | 8 | 8 |
| medication | 4 | 4 |
| **耗时** | **~8s** | **~1m47s** |

两个模型的抽取质量接近，v4-pro 耗时显著更长。对于此规模任务，`deepseek-chat` 性价比更高。

---

## 9. 集成对接：MinerU → LangExtract KG Pipeline **[实测]**

### 9.1 对接架构

```
MinerU 输出 (full.md + content_list.json)
    │
    ▼
[Format Bridge] — 按 section 边界分段的 PositionMap 构建
    │
    ▼
list[Document] (每 semantic section 一个)
    │
    ▼
[LangExtract + DeepSeek] → list[AnnotatedDocument]
    │
    ▼
[Grounding Resolver] — char_interval → bbox + page_idx
    │
    ▼
[KG Builder] → nodes.json + edges.json
```

### 9.2 代码路径

| 模块 | 路径 |
|---|---|
| Pipeline 编排器 | `D:\graghRAG-agent\integration\pipeline.py` |
| Format Bridge | `D:\graghRAG-agent\integration\bridge.py` |
| 接地解析 | `D:\graghRAG-agent\integration\grounding.py` |
| KG 构建 | `D:\graghRAG-agent\integration\kg_builder.py` |
| 数据模型 | `D:\graghRAG-agent\integration\schema.py` |
| Few-shot 示例 | `D:\graghRAG-agent\integration\config\extraction_examples.yaml` |
| 配置文件 | `D:\graghRAG-agent\integration\.env` |

### 9.3 运行方式

```bash
# 完整 Pipeline（MinerU 解析 + LangExtract 抽取 + KG 构建）
cd D:\graghRAG-agent\integration
source ../langextract/.venv/Scripts/activate
python pipeline.py --pdf ../mineru-mvp-test/sample.pdf

# 跳过 MinerU（使用缓存结果）
python pipeline.py --cached ../mineru-mvp-test/output/87bc1f56
```

### 9.4 2026-05-24 实测数据 (arXiv Transformer 论文, 15 页)

| 指标 | 值 |
|---|---|
| MinerU 解析 | task_id=87bc1f56, pipeline 后端 |
| full.md 长度 | 42,551 chars |
| content_list 项 | 141 项 |
| 分段数 | 24 sections |
| LangExtract 总抽取 | 310 entities |
| 接地实体 | 276 (89.0%) |
| Grounding 解析接地率 | 214 (69.0%) |
| KG 节点 | 310 |
| KG 边 | 1,529 |

**Top 5 实体类别:**

| 类别 | 数量 |
|---|---|
| reference | 76 |
| claim | 48 |
| model_component | 40 |
| metric | 35 |
| paper_metadata | 31 |

### 9.5 KG 输出格式

**nodes.json**: 每个节点含 `node_id`, `entity_type`, `label`, `properties`, `page_idx`, `bbox_norm`, `grounding_status`

**edges.json**: 每条边含 `edge_id`, `source_node_id`, `target_node_id`, `relation_type` (co_occurs_with / same_type / adjacent_to), `properties`

### 9.6 已知限制

- LaTeX 公式中的反斜杠可能导致 chunk 解析失败（LangExtract YAML parser 报 `Invalid \escape`），chunk 自动跳过不阻塞 pipeline
- PositionMap 的文本匹配精度约 69%（Stage 4），可通过改进 content_list 对齐算法提升
- 边缘关系目前为启发式规则（共现/邻接/同类型），不涉及 LLM 推断

## 附录 A：参考链接

- LangExtract GitHub: https://github.com/google/langextract
- DeepSeek API 文档: https://api-docs.deepseek.com
- 环境规范: `D:\graghRAG-agent\langextract\CLAUDE.md`
- 集成 Pipeline: `D:\graghRAG-agent\integration\pipeline.py`

## 附录 B：文档修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-24 | 基于 DeepSeek MVP 实测完成：新增 Pipeline 执行流程、实测输出文件清单、DeepSeek 兼容性配置、关键参数详解、虚拟环境说明 |
