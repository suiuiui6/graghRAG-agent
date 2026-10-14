> 项目名称：GraphRAG Agent 多模态知识图谱 RAG 系统  
> 拟申请方向：发明专利  
> 本材料用途：帮助专利代理人快速理解项目内容、核心技术方案、可能的申请点和需要重点检索/判断的问题。  
> 说明：本材料是技术沟通稿，不是正式专利申请文件；正式权利要求和公开风险判断请以代理人检索和法律意见为准。

## 1. 我想申请什么

我希望基于一个已经实现并实测过的多模态文档知识图谱问答项目，评估是否可以申请发明专利。

项目的核心不是普通的“上传文档后用大模型问答”，而是围绕以下技术链路：

```text
多模态文档解析
  -> 内容块与全文字符位置映射
  -> 文档片段切分
  -> 大模型实体抽取
  -> 抽取实体回溯到原始文档页码和版面坐标
  -> 构建带接地状态的知识图谱
  -> 基于接地知识图谱进行可溯源问答
  -> 返回答案、引用节点、页码和 bbox 坐标
```

我最希望代理人判断的是：

1. 是否可以围绕完整方案申请发明专利。
2. 如果完整方案因公开风险或现有技术风险较高，是否可以改为申请更窄的改进点。
3. 哪个申请点最适合用于保研/升学材料，即技术性强、授权可能性相对更高、能体现本人贡献。

## 2. 项目一句话概括

本项目是一套面向 PDF、Word、PPT、图片等多模态文档的知识图谱 RAG 系统，能够从原始文档中解析内容、抽取实体、构建知识图谱，并在问答时返回可定位到原始文档具体页码和版面坐标区域的证据链。

简化表达：

```text
上传文档 -> 自动解析 -> 抽取实体 -> 实体接地到 page_idx + bbox -> 构建 KG -> 基于 KG 问答 -> 答案可溯源到原文位置
```

## 3. 项目解决的问题

现有 RAG 或文档问答系统常见问题包括：

1. 只能返回答案或文本片段，难以精确定位答案依据在原始 PDF/文档的具体页面区域。
2. 大模型抽取出的实体可能无法在原文中定位，存在幻觉或不可验证问题。
3. 普通知识图谱节点通常只保存实体和关系，不保存该实体在原始文档中的页码、bbox 坐标、内容块类型和接地状态。
4. 多模态文档中包含标题、段落、表格、公式、图片说明等不同内容块，直接转成纯文本后容易丢失版面信息。
5. 问答结果缺少结构化证据链，用户难以审查答案是否真实来自原始文档。

本项目的目标是建立一条从“文档解析结果”到“问答答案引用”的连续接地链路，使关键答案能够追溯到原始文档的 `page_idx` 和 `bbox`。

## 4. 当前实现的主要技术流程

### 4.1 文档解析阶段

输入文档通过 MinerU 等文档解析服务处理，得到：

- `full.md`：完整 Markdown 文本，按文档阅读顺序组织。
- `content_list.json`：平铺内容块列表，包含文本块、表格块、公式块、图片块、图表块等。
- `layout.json`：页面级或块级版面布局信息。
- 每个内容块通常带有 `page_idx` 和 `bbox`。

其中 `bbox` 是文档页面中的版面坐标，项目中统一使用或转换为 0-1000 归一化坐标。

### 4.2 内容块到全文的 PositionMap 构建

系统遍历 `content_list.json` 中的每个内容块，提取可显示文本，然后在 `full.md` 中匹配该文本位置，构建 `PositionMap`。

`PositionMap` 的作用是建立：

```text
full.md 字符区间 -> content_list item -> page_idx + bbox + block_type
```

对不同内容块的处理方式包括：

- 文本块：取 `text` 字段。
- 表格块：取 `table_caption` 或表格说明。
- 公式块：取公式文本。
- 图片块：取 `image_caption` 或占位文本。
- 图表块：取 `chart_caption` 或占位文本。

匹配前会做空白字符归一化。如果完整文本无法匹配，可以使用前缀匹配或回退位置生成弱映射，避免整个流程中断。

### 4.3 文档片段切分

系统根据标题层级对 `full.md` 做 section 切分，例如按 H1/H2 边界切分。每个 section 会记录：

- `document_id`
- section 标题
- 标题层级
- 在 `full.md` 中的 `char_start`
- 在 `full.md` 中的 `char_end`

这些 section 会作为后续实体抽取模型的输入。系统同时保存：

```text
document_id -> section 在 full.md 中的全局起始偏移
```

这个偏移是后续实体接地的关键。

### 4.4 实体抽取

系统调用 LangExtract + DeepSeek 或其他大模型，对每个 section 做结构化实体抽取，得到：

- `extraction_class`：实体类别。
- `extraction_text`：实体文本。
- `attributes`：实体属性。
- `char_interval`：实体在当前 section 内的字符区间。
- `alignment_status`：实体文本与原文的对齐状态。

实体类别包括但不限于：

- 文档元信息
- 章节标题
- 模型组件
- 数值指标
- 数据集
- 方法
- 定义
- 公式
- 参考文献
- 结论或论断

### 4.5 抽取实体的版面坐标接地

由于实体抽取得到的 `char_interval` 是 section 内的相对字符区间，系统会执行两级映射：

```text
section 内 char_interval
  -> 加上 section 全局起始偏移
  -> 得到 full.md 全局字符区间
  -> 查询 PositionMap
  -> 得到 page_idx + bbox + block_type
```

如果实体存在 `char_interval` 且能够匹配到 `PositionMap`，则标记为：

```text
grounding_status = grounded
```

并记录：

```text
page_idx
bbox_norm
block_type
```

如果实体没有 `char_interval`，或无法匹配到位置映射表，则标记为：

```text
grounding_status = ungrounded
page_idx = null
bbox_norm = null
```

### 4.6 知识图谱构建

系统将每个实体转换成知识图谱节点。节点包含：

- `node_id`
- `entity_type`
- `label`
- `properties`
- `page_idx`
- `bbox_norm`
- `grounding_status`

系统再基于启发式规则构建边：

- 同页共现：同一 `page_idx` 的实体之间建立 `co_occurs_with` 关系。
- 同类型顺连：同一实体类型的连续实体之间建立 `same_type` 关系。
- 顺序邻接：抽取顺序相邻的实体建立 `adjacent_to` 关系。

边保留 `rule` 属性，用于解释边的来源。

### 4.7 Agentic KG-RAG 问答

问答阶段使用知识图谱作为主要检索对象。系统加载 `nodes.json` 和 `edges.json`，构建 NetworkX 图结构，并可以筛选出 `G_grounded` 子图。

问答工具包括：

- 按实体类型和关键词搜索节点。
- 查询实体 k-hop 邻居。
- 获取实体详情。
- 获取全局知识图谱统计。

问答策略包括：

- 数值/指标类问题优先检索 `metric` 节点。
- 结构/关系类问题优先做图谱邻域遍历。
- 概念/定义类问题优先检索 `definition` 节点。
- 元数据类问题优先检索 `paper_metadata` 节点。

最终回答中会包含：

- 自然语言答案。
- 引用的知识图谱节点 ID。
- 页码。
- bbox 坐标。
- 相关子图或 source 列表。

## 5. 关键数据结构

### 5.1 内容块

```json
{
  "type": "text",
  "text": "示例文本",
  "text_level": 2,
  "bbox": [120, 200, 880, 350],
  "page_idx": 0
}
```

### 5.2 PositionMap 映射项

```json
{
  "char_start": 1024,
  "char_end": 1150,
  "source_item_idx": 12,
  "page_idx": 0,
  "bbox": [120, 200, 880, 350],
  "block_type": "text",
  "text_level": 2,
  "text": "示例文本"
}
```

### 5.3 接地实体

```json
{
  "extraction_class": "metric",
  "extraction_text": "28.4 BLEU",
  "attributes": {
    "name": "BLEU",
    "value": "28.4",
    "task": "translation"
  },
  "char_interval": [5600, 5609],
  "page_idx": 0,
  "bbox_norm": [150, 400, 280, 415],
  "block_type": "text",
  "grounding_status": "grounded"
}
```

### 5.4 知识图谱节点

```json
{
  "node_id": "n0019",
  "entity_type": "metric",
  "label": "28.4 BLEU",
  "properties": {
    "name": "BLEU",
    "value": "28.4",
    "task": "translation"
  },
  "page_idx": 0,
  "bbox_norm": [150, 400, 280, 415],
  "grounding_status": "grounded"
}
```

### 5.5 知识图谱边

```json
{
  "edge_id": "e0001",
  "source_node_id": "n0019",
  "target_node_id": "n0020",
  "relation_type": "co_occurs_with",
  "properties": {
    "rule": "same_page",
    "page_idx": 0
  }
}
```

## 6. 已实测数据

项目已用 Transformer 论文 PDF 做过端到端 MVP 测试。

实测数据：

- 输入文档：arXiv Transformer 论文，15 页。
- `full.md` 长度：约 42,551 字符。
- `content_list` 项数：约 141 项。
- section 切分结果：24 个 section。
- 实体抽取总数：310 个实体。
- Stage 3 raw grounded：276 个，约 89.0%。
- Stage 4 resolved grounded：214 个，约 69.0%。
- 知识图谱节点：310 个。
- 知识图谱边：1,529 条。
- 总 Pipeline 耗时：约 49 秒。

典型问答：

```text
问题：What BLEU scores did the Transformer achieve and on which datasets?

回答中返回：
- 28.4 BLEU，对应 WMT 2014 EN-DE。
- 41.8 BLEU，对应 WMT 2014 EN-FR。
- 每个指标关联 KG 节点 ID、page_idx 和 bbox。
```

## 7. 我认为可能的专利申请点

### 7.1 大方案申请点

拟申请名称：

```text
一种基于版面坐标接地的多模态文档知识图谱构建与可溯源问答方法、装置、设备及存储介质
```

核心保护对象：

```text
文档解析结果 -> PositionMap -> section 切分 -> 实体抽取 -> 实体接地 -> grounded KG -> 可溯源问答
```

该方向覆盖完整系统，表达效果较好，但如果申请日前已有项目文档或代码公开，可能存在新颖性风险，请代理人重点评估。

### 7.2 窄改进点 1：基于分段字符偏移的实体版面坐标接地方法

拟申请名称：

```text
一种基于分段字符偏移的文档实体版面坐标接地方法、装置、设备及存储介质
```

核心技术点：

```text
LLM 抽取结果中的 section 内 char_interval
  -> 加上 section 全局偏移
  -> 转换为 full.md 全局字符区间
  -> 查询 PositionMap
  -> 得到 page_idx + bbox + block_type
```

技术效果：

- 解决 LLM 抽取实体无法稳定回溯到原始文档页面区域的问题。
- 使实体抽取结果可以与原始文档版面坐标绑定。
- 为后续知识图谱可溯源检索和前端高亮提供基础。

### 7.3 窄改进点 2：面向多模态解析结果的 PositionMap 弱匹配构建方法

拟申请名称：

```text
一种面向多模态文档解析结果的鲁棒位置映射表构建方法、装置、设备及存储介质
```

核心技术点：

- 从文本块、表格块、公式块、图片说明块等不同内容块中提取可匹配文本。
- 对可匹配文本进行空白字符归一化。
- 在全文文本中查找完整匹配。
- 完整匹配失败时执行前缀匹配。
- 仍无法匹配时，基于前一映射项结束位置生成弱映射项。

技术效果：

- 在解析结果和全文文本不完全一致时，仍可构建可用的位置映射表。
- 提高后续实体接地流程的鲁棒性。

### 7.4 窄改进点 3：基于接地状态的知识图谱节点筛选与可信问答方法

拟申请名称：

```text
一种基于接地状态的知识图谱节点筛选与可信文档问答方法、装置、设备及存储介质
```

核心技术点：

- 将实体分为 `grounded` 和 `ungrounded`。
- 知识图谱节点保留接地状态。
- 问答检索优先或仅使用 `grounded` 节点。
- 对无法接地实体进行过滤、降权或单独展示。

技术效果：

- 降低大模型幻觉实体进入问答结果的概率。
- 提高答案可验证性。
- 让系统能够明确区分“可回溯事实”和“不可回溯实体”。

### 7.5 窄改进点 4：基于 page_idx + bbox 的答案证据高亮联动方法

拟申请名称：

```text
一种面向文档问答结果的版面级证据定位与交互展示方法、装置、设备及存储介质
```

核心技术点：

- 问答结果返回 source node。
- source node 绑定 `page_idx` 和 `bbox_norm`。
- 前端根据页码和 bbox 定位原始文档区域。
- 点击答案引用时，高亮原始文档中的证据区域。

技术效果：

- 提高用户审查答案依据的效率。
- 使 RAG 答案从“文本引用”变为“版面区域引用”。

## 8. 目前我最推荐优先评估的点

我建议代理人优先评估：

```text
一种基于分段字符偏移的文档实体版面坐标接地方法、装置、设备及存储介质
```

原因：

1. 它比完整 KG-RAG 系统更窄，技术问题更集中。
2. 它直接解决大模型抽取实体与原始文档版面坐标之间的映射问题。
3. 它可以作为后续知识图谱构建、证据高亮和可溯源问答的核心基础。
4. 即使完整系统方案存在公开风险，该窄点仍值得检索是否可单独主张。

## 9. 关于公开风险的说明

该项目曾使用 GitHub 仓库进行代码和文档管理。仓库目前已经设置为私有。

需要代理人注意：

- 该仓库在申请前可能曾短暂处于公开状态。
- 公开时的内容可能包含项目文档、架构说明、代码或部分核心流程。
- 目前不确定公开期间是否被第三方访问、缓存、复制、截图或传播。
- 我希望代理人按“存在申请前公开风险”来评估，而不是默认完全未公开。

请代理人重点判断：

1. 如果完整方案在申请日前已经被公开，是否会影响大方案申请。
2. 公开内容是否已经充分公开 `PositionMap -> 实体接地 -> grounded KG -> 可溯源问答` 的完整链路。
3. 是否仍可围绕更窄的未充分公开改进点进行申请。
4. 是否需要重新组织权利要求，把重点从完整系统收缩到具体技术机制。

## 10. 希望代理人重点检索的关键词

中文关键词：

- 文档问答溯源
- 多模态文档知识图谱
- 文档实体接地
- 文档版面坐标映射
- 文档 bbox 溯源
- 知识图谱检索增强生成
- 可溯源问答
- 文档页面高亮引用
- 大模型实体抽取位置映射

英文关键词：

- document entity grounding
- layout-aware document understanding
- bbox grounding
- page-level evidence retrieval
- source-grounded question answering
- knowledge graph retrieval augmented generation
- GraphRAG source citation
- document QA evidence highlighting
- character offset to bounding box mapping
- multimodal document knowledge graph

## 11. 可提供给代理人的项目文件

以下文件可以作为技术交底和实施例支撑：

- `docs/patent/patent-disclosure-grounded-kg-rag.md`
- `langextract/docs/bridge-pipeline-specification-v1.0.md`
- `langextract/docs/agentic-kg-rag-specification-v1.0.md`
- `integration/Agentic-RAG-Architecture.md`
- `integration/backend-api-architecture-v1.0.md`
- `integration/bridge.py`
- `integration/grounding.py`
- `integration/kg_builder.py`
- `integration/agentic_rag_mvp.py`

## 12. 我希望代理人给出的结论

请代理人帮忙判断：

1. 大方案是否仍值得申请。
2. 如果大方案风险较高，最适合申请的窄改进点是哪一个。
3. 是否建议以发明专利形式申请，还是转向软著、论文或技术报告。
4. 如果申请，建议的专利名称、独立权利要求保护范围和从属权利要求布局是什么。
5. 是否需要先做现有技术检索和 GitHub 公开风险检索。
6. 对升学/保研材料来说，受理、公开、授权各阶段分别能提供多大证明价值。

## 13. 我希望在申请中体现的个人贡献

我希望材料中能体现本人在以下方面的技术贡献：

- 设计多模态文档解析结果到知识图谱构建的整体 Pipeline。
- 设计 `content_list -> full.md -> PositionMap` 的位置映射方法。
- 设计 `section char_interval -> global offset -> page_idx + bbox` 的实体接地流程。
- 设计带 `grounding_status` 的知识图谱节点结构。
- 设计基于 grounded KG 节点的可溯源问答方式。
- 完成 MVP 实测和相关规范文档整理。

可用于简历或保研材料的表述：

```text
围绕多模态文档知识图谱问答系统，设计并实现了文档解析结果与大模型实体抽取结果之间的版面坐标接地链路，提出基于 page_idx + bbox 的 grounded KG-RAG 问答方法，使系统能够在生成自然语言答案的同时返回可定位到原始文档页面区域的证据链。
```
