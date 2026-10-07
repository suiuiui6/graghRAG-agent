# GraphRAG Agent 专利代理人沟通材料

> 项目名称：GraphRAG Agent 多模态知识图谱 RAG 系统  
> 拟申请类型：发明专利  
> 建议优先评估方向：基于分段字符偏移的文档实体版面坐标接地方法  
> 材料用途：帮助专利代理人快速理解项目内容、核心技术方案、可申请点、公开风险和后续检索重点。  
> 说明：本文为技术沟通与交底材料，不构成法律意见；正式申请文件、权利要求范围和公开风险判断以专利代理人检索和法律意见为准。

## 1. 项目一句话概括

本项目是一套面向 PDF、Word、PPT、图片等多模态文档的知识图谱 RAG 系统，能够从原始文档中解析内容、抽取实体、构建知识图谱，并在问答时返回可定位到原始文档具体页码和版面坐标区域的证据链。

简化流程如下：

```text
上传文档
  -> 多模态文档解析
  -> 构建 content_list 到 full.md 的位置映射
  -> 按标题层级切分文档片段
  -> 大模型实体抽取
  -> 实体 char_interval 映射到 page_idx + bbox
  -> 构建带 grounding_status 的知识图谱
  -> 基于 grounded KG 进行可溯源问答
  -> 返回答案、引用节点、页码和 bbox 坐标
```

项目核心不是普通的“上传文档后用大模型问答”，而是建立一条从文档解析结果到知识图谱节点、再到问答引用结果的连续接地链路，使关键答案能够回溯到原始文档的 `page_idx` 和 `bbox`。

## 2. 要解决的技术问题

现有 RAG 或文档问答系统通常只能返回答案、文本片段或粗粒度引用，存在以下问题：

1. 文档解析结果与大模型实体抽取结果之间缺少稳定的位置映射关系，导致实体和答案难以定位到原始 PDF 或文档页面区域。
2. 多模态文档中的标题、段落、表格、公式、图片说明和版面坐标在纯文本化过程中容易丢失。
3. 普通知识图谱节点通常只保存实体和关系，不保存实体在原始文档中的页码、bbox 坐标、内容块类型和接地状态。
4. 大模型可能抽取出无法在原文中定位的实体，带来幻觉实体进入知识图谱和问答链路的风险。
5. 问答结果缺少结构化证据链，用户难以审查答案是否真实来自原始文档。

本项目希望解决的核心问题是：如何将大模型抽取出的文档实体稳定映射回原始文档的页面和版面坐标，并基于这些已接地实体构建可溯源知识图谱问答系统。

## 3. 核心技术方案

### 3.1 文档解析

输入文档通过 MinerU 等文档解析服务处理，得到：

- `full.md`：按照阅读顺序组织的完整 Markdown 文本。
- `content_list.json`：平铺内容块列表，包含文本块、表格块、公式块、图片块、图表块等。
- `layout.json`：页面级或块级版面布局信息。

每个内容块通常携带：

- `page_idx`：页码索引。
- `bbox`：该内容块在页面中的版面坐标。
- `type`：内容块类型，例如文本、表格、公式或图片说明。

项目中可将 bbox 统一转换为 0-1000 归一化坐标，便于跨文档和前端展示使用。

### 3.2 PositionMap 位置映射表

系统遍历 `content_list.json` 中的每个内容块，提取可显示文本，并在 `full.md` 中匹配该文本位置，构建 `PositionMap`。

`PositionMap` 建立如下对应关系：

```text
full.md 字符区间 -> content_list item -> page_idx + bbox + block_type
```

对不同内容块可采用不同文本提取方式：

- 文本块：使用 `text` 字段。
- 表格块：使用表格标题、表格说明或表格文本。
- 公式块：使用公式文本。
- 图片块：使用图片说明或占位文本。
- 图表块：使用图表标题或说明。

匹配前可进行空白字符归一化。若完整文本无法匹配，可使用前缀匹配；若仍无法匹配，则基于前一映射项结束位置生成弱映射项，避免整个流程中断。

### 3.3 文档片段切分

系统根据标题层级或语义段落边界对 `full.md` 进行 section 切分。每个 section 记录：

- `document_id`
- section 标题
- 标题层级
- 在 `full.md` 中的 `char_start`
- 在 `full.md` 中的 `char_end`

这些 section 作为后续实体抽取模型的输入。系统同时保存每个 section 在全文中的全局起始偏移，这是实体接地的关键。

### 3.4 实体抽取

系统调用 LangExtract + DeepSeek 或其他大模型，对每个 section 做结构化实体抽取，得到：

- `extraction_class`：实体类别。
- `extraction_text`：实体文本。
- `attributes`：实体属性。
- `char_interval`：实体在当前 section 内的字符区间。
- `alignment_status`：实体文本与原文的对齐状态。

实体类别可包括文档元信息、章节标题、模型组件、数值指标、数据集、方法、定义、公式、参考文献、结论或论断等。

### 3.5 实体版面坐标接地

由于实体抽取得到的 `char_interval` 是 section 内的相对字符区间，系统执行两级映射：

```text
section 内 char_interval
  -> 加上 section 全局起始偏移
  -> 得到 full.md 全局字符区间
  -> 查询 PositionMap
  -> 得到 page_idx + bbox + block_type
```

若实体存在 `char_interval` 且能匹配到 `PositionMap`，则标记为：

```text
grounding_status = grounded
```

并记录：

```text
page_idx
bbox_norm
block_type
```

若实体没有 `char_interval`，或无法匹配到位置映射表，则标记为：

```text
grounding_status = ungrounded
page_idx = null
bbox_norm = null
```

### 3.6 接地知识图谱构建

系统将每个实体转换为知识图谱节点。节点保留：

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

### 3.7 可溯源 KG-RAG 问答

问答阶段使用知识图谱作为主要检索对象。系统加载 `nodes.json` 和 `edges.json`，构建图结构，并可筛选出只包含已接地节点的 `G_grounded` 子图。

问答策略包括：

- 数值或指标类问题优先检索 `metric` 节点。
- 结构或关系类问题优先执行图谱邻域遍历。
- 概念或定义类问题优先检索 `definition` 节点。
- 元数据类问题优先检索 `paper_metadata` 节点。
- 问答检索可优先或仅使用 `grounded` 节点，对 `ungrounded` 节点过滤、降权或单独展示。

最终回答包含：

- 自然语言答案。
- 引用的知识图谱节点 ID。
- 页码。
- bbox 坐标。
- 相关子图或 source 列表。

前端可根据 `page_idx + bbox_norm` 在原始文档预览区域高亮答案依据。

## 4. 关键数据结构

### 4.1 内容块

```json
{
  "type": "text",
  "text": "示例文本",
  "text_level": 2,
  "bbox": [120, 200, 880, 350],
  "page_idx": 0
}
```

### 4.2 PositionMap 映射项

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

### 4.3 接地实体

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

### 4.4 知识图谱节点

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

### 4.5 知识图谱边

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

## 5. 已实测实施例

项目已使用 Transformer 论文 PDF 做过端到端 MVP 测试。

实测数据如下：

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

## 6. 建议优先评估的专利申请点

### 6.1 优先推荐：基于分段字符偏移的文档实体版面坐标接地方法

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

推荐原因：

1. 该方案比完整 KG-RAG 系统更窄，技术问题更集中。
2. 该方案直接解决大模型抽取实体无法稳定回溯到原始文档页面区域的问题。
3. 该方案可作为知识图谱构建、证据高亮和可溯源问答的基础机制。
4. 即使完整系统存在公开风险，该窄点仍值得单独检索和评估。

### 6.2 备选申请点：面向多模态解析结果的 PositionMap 弱匹配构建方法

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

### 6.3 备选申请点：基于接地状态的知识图谱节点筛选与可信问答方法

拟申请名称：

```text
一种基于接地状态的知识图谱节点筛选与可信文档问答方法、装置、设备及存储介质
```

核心技术点：

- 将实体分为 `grounded` 和 `ungrounded`。
- 知识图谱节点保留接地状态。
- 问答检索优先或仅使用 `grounded` 节点。
- 对无法接地实体进行过滤、降权或单独展示。

### 6.4 备选申请点：基于 page_idx + bbox 的答案证据高亮联动方法

拟申请名称：

```text
一种面向文档问答结果的版面级证据定位与交互展示方法、装置、设备及存储介质
```

核心技术点：

- 问答结果返回 source node。
- source node 绑定 `page_idx` 和 `bbox_norm`。
- 前端根据页码和 bbox 定位原始文档区域。
- 点击答案引用时，高亮原始文档中的证据区域。

### 6.5 完整系统申请点

拟申请名称：

```text
一种基于版面坐标接地的多模态文档知识图谱构建与可溯源问答方法、装置、设备及存储介质
```

完整系统覆盖：

```text
文档解析结果
  -> PositionMap
  -> section 切分
  -> 实体抽取
  -> 实体接地
  -> grounded KG
  -> 可溯源问答
```

该方向表达效果较完整，但若申请日前已有项目文档或代码公开，可能存在新颖性风险，建议代理人重点评估。

## 7. 可建议权利要求布局

### 7.1 独立权利要求方向

一种基于版面坐标接地的多模态文档知识图谱构建与可溯源问答方法，可包括：

1. 获取待处理文档的解析结果，所述解析结果包括文档全文文本、内容块列表以及各内容块对应的页码和版面坐标。
2. 根据内容块列表中的文本内容在文档全文文本中的字符位置，构建位置映射表，所述位置映射表记录字符区间与页码、版面坐标、内容块类型之间的对应关系。
3. 按照标题层级或语义段落边界对文档全文文本进行切分，得到多个文档片段，并记录各文档片段在文档全文文本中的全局字符偏移。
4. 对文档片段进行实体抽取，得到包含实体类别、实体文本、实体属性和片段内字符区间的抽取结果。
5. 根据全局字符偏移将片段内字符区间转换为全文全局字符区间，并基于位置映射表确定实体对应的页码和版面坐标。
6. 根据实体、页码、版面坐标和接地状态构建知识图谱节点，并根据共现关系、同类型关系或顺序邻接关系构建知识图谱边。
7. 接收用户查询，基于知识图谱执行检索和问答生成，输出包含答案文本、知识图谱节点标识、页码和版面坐标的可溯源问答结果。

### 7.2 从属权利要求方向

可围绕以下方向展开：

1. 内容块列表包括文本块、表格块、公式块、图片块或图表块中的至少一种。
2. 构建位置映射表时对内容块文本进行空白字符归一化。
3. 当完整内容块文本无法匹配时，使用预设长度前缀进行匹配。
4. 当内容块无法匹配时，基于前一映射项结束位置生成弱映射项。
5. 文档片段按照一级标题、二级标题或预设标题层级进行切分。
6. 当文档片段长度低于预设阈值时，将该文档片段合并至相邻文档片段。
7. 当实体抽取结果缺少字符区间或无法匹配位置映射表时，将该实体标记为未接地实体。
8. 知识图谱检索阶段优先检索接地状态为已接地的知识图谱节点。
9. 共现关系根据实体对应的页码是否相同确定。
10. 可溯源问答结果用于在文档预览界面中根据页码和版面坐标高亮显示答案依据区域。

### 7.3 装置、设备和存储介质权利要求

可进一步撰写：

- 一种基于版面坐标接地的多模态文档知识图谱构建与可溯源问答装置。
- 一种电子设备，包括处理器和存储器，存储器中的程序被处理器执行时实现上述方法。
- 一种计算机可读存储介质，其上存储的程序被处理器执行时实现上述方法。

## 8. 公开风险说明

该项目曾使用 GitHub 仓库进行代码和文档管理，仓库目前已经设置为私有。

需要代理人注意：

1. 该仓库在申请前可能曾短暂处于公开状态。
2. 公开时的内容可能包含项目文档、架构说明、代码或部分核心流程。
3. 目前不确定公开期间是否被第三方访问、缓存、复制、截图或传播。
4. 建议按“存在申请前公开风险”进行评估，而不是默认完全未公开。

请代理人重点判断：

1. 如果完整方案在申请日前已经被公开，是否会影响完整系统方案申请。
2. 公开内容是否已经充分公开 `PositionMap -> 实体接地 -> grounded KG -> 可溯源问答` 的完整链路。
3. 是否仍可围绕更窄、未充分公开或技术特征更具体的改进点进行申请。
4. 是否需要将权利要求重点从完整系统收缩到“分段字符偏移实体接地”这一具体技术机制。

## 9. 希望代理人重点检索的问题和关键词

### 9.1 重点检索问题

请代理人重点判断：

1. 是否已有将 LLM 抽取实体的字符区间映射到文档页码和 bbox 的公开方案。
2. 是否已有基于 grounded 节点构建知识图谱并用于 RAG 问答的公开方案。
3. 是否已有相同或近似的 `content_list -> full.md -> PositionMap` 构建方式。
4. 完整 KG-RAG 系统和窄点实体接地方法分别是否具备新颖性、创造性和实用性。
5. 若公开风险存在，哪些申请点仍有保留价值。

### 9.2 中文关键词

- 文档问答溯源
- 多模态文档知识图谱
- 文档实体接地
- 文档版面坐标映射
- 文档 bbox 溯源
- 知识图谱检索增强生成
- 可溯源问答
- 文档页面高亮引用
- 大模型实体抽取位置映射

### 9.3 英文关键词

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

## 10. 可提供给代理人的项目材料

以下文件可作为技术支撑和实施例材料：

- `docs/patent/patent-disclosure-grounded-kg-rag.md`
- `docs/patent/patent-agent-summary-for-attorney.md`
- `langextract/docs/bridge-pipeline-specification-v1.0.md`
- `langextract/docs/agentic-kg-rag-specification-v1.0.md`
- `integration/Agentic-RAG-Architecture.md`
- `integration/backend-api-architecture-v1.0.md`
- `integration/bridge.py`
- `integration/grounding.py`
- `integration/kg_builder.py`
- `integration/agentic_rag_mvp.py`

## 11. 希望代理人给出的结论

请代理人帮助判断：

1. 完整系统方案是否仍值得申请。
2. 如果完整系统方案风险较高，最适合申请的窄改进点是哪一个。
3. 是否建议以发明专利形式申请，还是转向软著、论文或技术报告。
4. 如果申请，建议的专利名称、独立权利要求保护范围和从属权利要求布局是什么。
5. 是否需要先做现有技术检索和 GitHub 公开风险检索。
6. 对升学或保研材料而言，受理、公开、授权各阶段分别能提供多大证明价值。

## 12. 个人贡献描述建议

申请人围绕多模态文档知识图谱问答系统，设计并实现了文档解析结果与大模型实体抽取结果之间的版面坐标接地链路，提出基于 `page_idx + bbox` 的 grounded KG-RAG 问答方法，使系统能够在生成自然语言答案的同时返回可定位到原始文档页面区域的证据链。

可拆分为以下贡献：

1. 设计多模态文档解析结果到知识图谱构建的整体 Pipeline。
2. 设计 `content_list -> full.md -> PositionMap` 的位置映射方法。
3. 设计 `section char_interval -> global offset -> page_idx + bbox` 的实体接地流程。
4. 设计带 `grounding_status` 的知识图谱节点结构。
5. 设计基于 grounded KG 节点的可溯源问答方式。
6. 完成 MVP 实测和相关规范文档整理。

## 13. 正式提交前建议补充的材料

正式让代理人撰写申请文件前，建议补齐：

1. 一组完整样例，包括输入文档、`content_list.json`、`full.md`、`PositionMap`、抽取实体、KG 节点和问答输出。
2. 项目核心流程图，至少包括整体架构图、实体接地图、知识图谱节点结构图和问答高亮展示图。
3. 前端问答证据高亮截图或原型图。
4. 申请日前是否公开代码或文档的时间线说明。
5. 发明人排序与各自贡献说明。
6. 目标学校或学院对专利受理、公开、授权材料的认定规则。
