# MinerU 云端 API 文档解析规范文档

> 基于 MinerU v4 云端 API (`mineru.net`) 调研结果，覆盖输入格式、输出格式、布局信息及 MVP 测试参数规范。

---

## 目录

1. [MinerU 支持的原始输入文件格式](#1-mineru-支持的原始输入文件格式)
2. [云端 API 方案：输出格式与生成文件详解](#2-云端-api-方案输出格式与生成文件详解)
3. [布局信息详解：为精准数值提取提供支撑](#3-布局信息详解为精准数值提取提供支撑)
4. [MVP 测试：必要字段与必传参数](#4-mvp-测试必要字段与必传参数)

---

## 1. MinerU 支持的原始输入文件格式

### 1.1 本地部署 vs 云端 API 输入能力

| 格式 | 本地 CLI/API | 云端 API (v4) | 说明 |
|---|---|---|---|
| **PDF** (`*.pdf`) | ✅ | ✅ | 核心格式，含扫描版自动 OCR |
| **Word** (`*.docx`) | ✅ (v1.0+) | ✅ | 原生解析 XML 结构 |
| **Word** (`*.doc`) | ✅ | ✅ | 旧版格式 |
| **PowerPoint** (`*.pptx`) | ✅ (v3.x) | ✅ | 原生解析 |
| **PowerPoint** (`*.ppt`) | ⚠️ 部分 | ✅ | 旧版需先转 PDF |
| **Excel** (`*.xlsx`) | ✅ (v3.x) | ✅ | 表格解析 |
| **图片** (`*.png`, `*.jpg`, `*.jpeg`) | ✅ | ✅ | 直接图片输入 |
| **HTML 网页** | ✅ | ✅ | 网页内容提取 |
| **EPUB 电子书** | ✅ | ✅ | 电子书格式 |

### 1.2 云端 API 文件大小限制

| 项目 | 限制 |
|---|---|
| 单文件大小 | ≤ 200 MB |
| 单文件页数 | ≤ 600 页 |
| 免费额度 | 每日 2000 页高优先级 |
| 文件有效期 | 30 天 |

### 1.3 文件传入方式

云端 API 支持**两种**传入方式。此前本节写"不支持直接上传文件"——**该说法已过时**
（2026-09-18 实测推翻），保留此处更正以免误导。

#### 方式 A：公网 URL（`url` 参数）

需先将文件托管到公网可访问的 URL，通过请求参数 `url` 传入。

```json
{
    "url": "https://example.com/path/to/document.pdf"
}
```

#### 方式 B：文件直传（`/file-urls/batch`）—— 本地文件的推荐方式

无需自建对象存储。三步：

**① 申请预签名上传 URL**
```
POST https://mineru.net/api/v4/file-urls/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "enable_formula": true,
  "language": "ch",
  "model_version": "pipeline",
  "files": [{"name": "x.pdf", "is_ocr": true}]
}
```
响应：
```json
{
  "code": 0, "msg": "ok", "trace_id": "...",
  "data": {
    "batch_id": "39d09f3d-...",
    "file_urls": ["https://mineru.oss-cn-shanghai.aliyuncs.com/...?<签名>"]
  }
}
```

**② PUT 上传文件到该 URL**
```
curl -X PUT --upload-file ./x.pdf "<file_urls[0]>"
```
⚠️ **不带 `Authorization` 头** —— 签名已内嵌在 URL 里，带上反而可能被拒。
⚠️ **URL 有时效**（签名含 `Expires`）。申请后应立即上传；上传失败要**重新申请**，
不要重放同一个 URL。

**③ 轮询批次结果**
```
GET https://mineru.net/api/v4/extract-results/batch/{batch_id}
Authorization: Bearer <token>
```
响应（注意与单任务端点形状**不同**）：
```json
{"code": 0, "data": {"extract_result": [
  {"file_name": "x.pdf", "state": "done", "full_zip_url": "https://..."}
]}}
```

`state` 取值：`waiting-file` | `running` | `done` | `failed`。

**两种方式的选择**：本地文件优先方式 B（省去自建对象存储）；输入本身已是公网 URL
则用方式 A。

⚠️ `/file-urls/batch` 的响应形状与 `/extract/task/{id}` 不同 ——
前者是 `data.extract_result[0].state`，后者是 `data.state`。实现见
`backend/mineru_client.py` 的 `_POLL_PATH` 表。

---

### 1.4 MinerU 的失败形态（两套，实测确认）

| 形态 | 触发 | 响应体 | 判定依据 |
|---|---|---|---|
| **① HTTP 状态码非 2xx** | 401 鉴权失败 / 422 参数错 / 429 限流 / 5xx | **无 `code` 字段**，用**字符串** `msgCode`，如 `{"msgCode":"A0202","msg":"user authenticate failed","success":false}` | **HTTP 状态码** |
| **② HTTP 200 + 负数 `code`** | 业务失败，如 `-60023` = "该 URL 被区域法规限制、无法访问" | `{"code":-60023,"msg":"this URL is restricted by regional regulations and cannot be accessed"}` | body `code` |

**实现要点**：`curl -s` 默认**丢弃 HTTP 状态码**，只用它取响应体会导致 ① 被误判
（此前实测把真实 401 误分类成 UNKNOWN）。须用 `-w "\n%{http_code}"` 取回状态码。

---

## 2. 云端 API 方案：输出格式与生成文件详解

### 2.1 API 调用流程

```
提交任务                         轮询查询                        下载结果
POST /api/v4/extract/task  →  GET /api/v4/extract/task/{id}  →  解压 full_zip_url
    │                                │                               │
    └─ 返回 task_id                  └─ state: done                  └─ ZIP 包
                                        └─ full_zip_url
```

**API 基础地址**：`https://mineru.net/api/v4/extract/task`

**认证方式**：`Authorization: Bearer <your-token>`

### 2.2 第一步：提交解析任务

**请求方式**：`POST`

**请求头**：
```
Content-Type: application/json
Authorization: Bearer <token>
```

**提交成功响应**：
```json
{
    "code": 0,
    "data": {
        "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b436"
    },
    "msg": "ok",
    "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 2.3 第二步：轮询任务状态

**请求方式**：`GET /api/v4/extract/task/{task_id}`

**状态枚举**：

| state | 含义 |
|---|---|
| `pending` | 排队中 |
| `running` | 正在解析 |
| `converting` | 格式转换中 |
| `done` | 解析完成 |
| `failed` | 解析失败 |

**进行中响应**：
```json
{
    "code": 0,
    "data": {
        "task_id": "47726b6e-46ca-4bb9-******",
        "state": "running",
        "err_msg": "",
        "extract_progress": {
            "extracted_pages": 1,
            "total_pages": 2,
            "start_time": "2025-01-20 11:43:20"
        }
    },
    "msg": "ok",
    "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

**完成响应**：
```json
{
    "code": 0,
    "data": {
        "task_id": "47726b6e-46ca-4bb9-******",
        "state": "done",
        "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/018e53ad-d4f1-475d-b380-36bf24db9914.zip",
        "err_msg": ""
    },
    "msg": "ok",
    "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

### 2.4 第三步：ZIP 包文件清单

`full_zip_url` 指向的 ZIP 包解压后，包含以下文件：

| 文件名 | 对应内部名称 | 说明 |
|---|---|---|
| `full.md` | Markdown 输出 | 完整文档的 Markdown 格式解析结果 |
| `*_layout.json` | `middle.json` | 中间处理结果，按页组织的完整块结构（含被丢弃的页眉/页脚） |
| `*_model.json` | `model.json` | 模型推理的原始输出 |
| `*_content_list.json` | `content_list.json` | 按阅读顺序平铺的结构化内容列表 |

### 2.5 full.md — Markdown 输出

**说明**：所有后端统一输出的 Markdown 格式文档。

**特性**：
- 保留文档标题层级结构（`#` / `##` / `###`）
- 表格转换为 Markdown 表格语法
- 公式保留 LaTeX 语法（`$$...$$` 行间，`$...$` 行内）
- 图片以引用路径形式呈现
- 按阅读顺序组织内容

**示例片段**：
```markdown
# 第一章 绪论

## 1.1 研究背景

近年来，随着人工智能技术的快速发展...

| 指标 | 2023年 | 2024年 |
|------|--------|--------|
| 准确率 | 85.3% | 92.1% |
| 召回率 | 78.9% | 88.6% |

$$F_1 = \frac{2 \times P \times R}{P + R}$$

如图 1-1 所示，系统架构包含三个核心模块。
```

### 2.6 *_content_list.json — 内容列表

**说明**：按阅读顺序排列的平铺结构化内容列表。所有 `bbox` 坐标为 **0-1000 归一化坐标**。

**顶层结构**：JSON 数组，每个元素为一个内容项。

#### 2.6.1 type: "text" — 文本块

```json
{
    "type": "text",
    "text": "这是正文段落的文本内容，包含完整的句子。",
    "text_level": 0,
    "bbox": [120, 200, 880, 350],
    "page_idx": 0
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | 固定值 `"text"` |
| `text` | `string` | 段落纯文本内容 |
| `text_level` | `int` | 文本层级：`0`=正文, `1`=一级标题, `2`=二级标题, `3`=三级标题... |
| `bbox` | `[float, float, float, float]` | 包围框：`[x0, y0, x1, y1]`，坐标 0-1000 归一化 |
| `page_idx` | `int` | 所在页码（从 0 开始） |

#### 2.6.2 type: "table" — 表格块

```json
{
    "type": "table",
    "table_body": "<table>\n  <tr>\n    <td>...</td>\n  </tr>\n</table>",
    "table_caption": ["表 1-1 实验数据对比"],
    "table_footnote": ["注：数据来源为 2024 年度统计报告"],
    "img_path": "images/table_0.jpg",
    "bbox": [100, 400, 900, 700],
    "page_idx": 0
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | 固定值 `"table"` |
| `table_body` | `string` | 表格的 HTML 表示 |
| `table_caption` | `string[]` | 表格标题（数组，每个元素为一行标题文本） |
| `table_footnote` | `string[]` | 表格脚注（数组，每个元素为一行脚注文本） |
| `img_path` | `string` | 表格渲染截图的相对路径 |
| `bbox` | `[float, float, float, float]` | 包围框，0-1000 归一化 |
| `page_idx` | `int` | 所在页码 |

#### 2.6.3 type: "equation" — 公式块

```json
{
    "type": "equation",
    "text": "$$\\frac{d}{dx}\\int_a^x f(t)dt = f(x)$$",
    "text_format": "latex",
    "img_path": "images/equation_0.jpg",
    "bbox": [150, 350, 850, 380],
    "page_idx": 1
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | 固定值 `"equation"`（行间公式） |
| `text` | `string` | LaTeX 格式的公式字符串 |
| `text_format` | `string` | 公式格式，固定为 `"latex"` |
| `img_path` | `string` | 公式渲染截图的相对路径 |
| `bbox` | `[float, float, float, float]` | 包围框，0-1000 归一化 |
| `page_idx` | `int` | 所在页码 |

> 行内公式（inline equation）在 content_list 中直接嵌入到 `type: "text"` 的 `text` 字段中，以 `$...$` 包裹。

#### 2.6.4 type: "image" — 图片块

```json
{
    "type": "image",
    "img_path": "images/figure_0.jpg",
    "image_caption": ["图 1-1 系统架构示意图"],
    "bbox": [200, 100, 800, 500],
    "page_idx": 1
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | 固定值 `"image"` |
| `img_path` | `string` | 图片文件的相对路径 |
| `image_caption` | `string[]` | 图片标题（数组） |
| `bbox` | `[float, float, float, float]` | 包围框，0-1000 归一化 |
| `page_idx` | `int` | 所在页码 |

#### 2.6.5 type: "header" / "footer" — 页眉/页脚

**仅在 VLM/Hybrid 后端中出现**。Pipeline 后端会将页眉页脚归入 `layout.json` 的 `discarded_blocks`，不出现在 `content_list` 中。

```json
{
    "type": "header",
    "text": "第三章 系统设计",
    "bbox": [500, 10, 800, 40],
    "page_idx": 5
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | `"header"` 或 `"footer"` |
| `text` | `string` | 页眉/页脚文本 |
| `bbox` | `[float, float, float, float]` | 包围框，0-1000 归一化 |
| `page_idx` | `int` | 所在页码 |

#### 2.6.6 type: "list" / "code" / "algorithm" — 其他块类型

**VLM 后端扩展支持**：

```json
// 列表
{
    "type": "list",
    "text": "- 第一项\n- 第二项\n- 第三项",
    "bbox": [120, 300, 600, 480],
    "page_idx": 2
}

// 代码块
{
    "type": "code",
    "text": "def hello():\n    print('Hello, World!')",
    "bbox": [120, 300, 880, 520],
    "page_idx": 2
}
```

### 2.7 *_layout.json — 中间处理结果 (middle.json)

**说明**：按页组织的深层嵌套结构，是二次开发和精确定位的核心数据源。Pipeline 后端的 bbox 坐标为**原始像素值**；VLM 后端为 **0-1000 归一化坐标**。

#### 2.7.1 顶层结构

```json
{
    "_backend": "pipeline",
    "pdf_info": [
        {
            "page_idx": 0,
            "page_size": [1190, 1684],
            "para_blocks": [],
            "discarded_blocks": []
        }
    ]
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `_backend` | `string` | 解析后端：`"pipeline"` / `"vlm"` / `"hybrid"` |
| `pdf_info` | `array` | 按页组织的页面信息数组 |
| `pdf_info[n].page_idx` | `int` | 页码索引（从 0 开始） |
| `pdf_info[n].page_size` | `[int, int]` | 页面尺寸：`[宽度, 高度]`（pipeline 为像素，VLM 为 0-1000） |
| `pdf_info[n].para_blocks` | `array` | 主要内容块数组（按阅读顺序排列） |
| `pdf_info[n].discarded_blocks` | `array` | 被丢弃的内容块（页眉、页脚、页码等） |

#### 2.7.2 para_blocks 通用字段

每个块的基本结构：

```json
{
    "type": "text",
    "bbox": [120, 200, 880, 350],
    "angle": 0,
    "blocks": []
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | `string` | 块类型（见下方 BlockType 枚举） |
| `bbox` | `[float, float, float, float]` | 包围框 `[x0, y0, x1, y1]` |
| `angle` | `int` | 旋转角度：`0`/`90`/`180`/`270`（VLM 后端特有） |
| `blocks` | `array` | 子块数组，嵌套结构为 `block → lines → spans` |

#### 2.7.3 BlockType 完整枚举

| BlockType | 说明 | 后端支持 |
|---|---|---|
| `text` | 普通正文段落 | 所有后端 |
| `title` | 标题 | 所有后端 |
| `doc_title` | 文档标题 | Pipeline |
| `abstract` | 摘要 | Pipeline |
| `image` | 图片 | 所有后端 |
| `table` | 表格 | 所有后端 |
| `interline_equation` | 行间公式 | 所有后端 |
| `list` | 列表 | VLM / Hybrid |
| `code` | 代码块 | VLM / Hybrid |
| `algorithm` | 算法伪代码 | VLM / Hybrid |
| `header` | 页眉 | VLM（Pipeline 归入 discarded_blocks） |
| `footer` | 页脚 | VLM（Pipeline 归入 discarded_blocks） |
| `page_number` | 页码 | VLM（Pipeline 归入 discarded_blocks） |

#### 2.7.4 嵌套结构详解

```
para_blocks[i]
  ├── type: "table"
  ├── bbox: [x0, y0, x1, y1]
  ├── blocks: [                       ← 子块数组
  │     {
  │       "type": "table_body",        ← 子块类型：body / caption / footnote
  │       "bbox": [...],
  │       "lines": [                   ← 行数组
  │         {
  │           "bbox": [...],
  │           "spans": [               ← span 数组（最小粒度）
  │             {
  │               "bbox": [...],
  │               "content": "单元格文本",  ← text/title 类型有 content
  │               "type": "text",
  │               "score": 0.98
  │             },
  │             {
  │               "bbox": [...],
  │               "html": "<table>...</table>",  ← table 类型用 html
  │               "type": "table",
  │               "image_path": "images/xxx.jpg",
  │               "score": 0.894
  │             }
  │           ]
  │         }
  │       ]
  │     }
  │   ]
```

**Span 级别字段**：

| 字段 | 适用的 span type | 说明 |
|---|---|---|
| `bbox` | 所有 | span 包围框 |
| `content` | `text`, `title` | 文本内容 |
| `html` | `table` | 表格 HTML 字符串 |
| `image_path` | `table`, `image` | 图片/截图路径 |
| `type` | 所有 | span 类型：`"text"` / `"table"` / `"image"` / `"equation"` |
| `score` | 所有 | 置信度分数（0-1） |
| `latex` | `equation` | LaTeX 公式字符串 |

#### 2.7.5 discarded_blocks 说明

Pipeline 后端将页眉、页脚、页码自动识别并归入 `discarded_blocks`，不出现在 `content_list` 中。若需获取这些信息用于特定场景（如页眉中的章节名），应读取 `layout.json` 的此字段。

---

## 3. 布局信息详解：为精准数值提取提供支撑

### 3.1 坐标系统

| 后端 | bbox 坐标空间 | 原点 |
|---|---|---|
| `pipeline` | 原始像素值 | 页面左上角 (0, 0) |
| `vlm` / `hybrid` | 0-1000 归一化 | 页面左上角 (0, 0) |

**bbox 格式**：`[x0, y0, x1, y1]`
- `x0`：左边界
- `y0`：上边界
- `x1`：右边界
- `y1`：下边界

**内容坐标层级关系**：
```
page_size → para_blocks[i].bbox → blocks[j].bbox → lines[k].bbox → spans[m].bbox
  页面         段落/块              子块（标题/正文/脚注）   行             最小文本单元
```

### 3.2 数值提取可利用的布局信息

#### 3.2.1 利用 content_list 进行数值提取

`content_list` 中**表格块的结构化 HTML** 是数值提取的最佳入口：

```json
{
    "type": "table",
    "table_body": "<table><tr><td>85.3%</td><td>92.1%</td></tr></table>",
    "table_caption": ["表 1-1 实验数据对比"],
    "bbox": [100, 400, 900, 700],
    "page_idx": 0
}
```

**提取策略**：
- 解析 `table_body` 的 HTML 结构获取单元格数值
- 利用 `bbox` 坐标定位表格在页面中的位置
- 关联 `table_caption` 捕获表格语义标题
- `page_idx` 可回溯原始页面

#### 3.2.2 利用 layout.json 进行精确定位

当需要像素级精确定位时（如从扫描件中提取特定区域的数值），使用 `layout.json`：

- **para_blocks 阅读顺序**：块按阅读顺序排列，可直接遍历还原文档流
- **嵌套 span 级别**：每个 span 有独立的 bbox + content，可精确定位到行/词粒度
- **表格完整结构**：table_body / table_caption / table_footnote 分离存储，可单独提取
- **公式渲染图**：`image_path` 提供公式的渲染截图

#### 3.2.3 坐标归一化转换

Pipeline 后端输出为原始像素坐标。如需统一归一化：

```python
# 将像素坐标转为 0-1000 归一化
page_w, page_h = page["page_size"]
norm_x0 = pixel_x0 / page_w * 1000
norm_y0 = pixel_y0 / page_h * 1000
norm_x1 = pixel_x1 / page_w * 1000
norm_y1 = pixel_y1 / page_h * 1000
```

#### 3.2.4 布局信息在提取中的应用对照

| 提取场景 | 推荐数据源 | 利用字段 |
|---|---|---|
| 表格数值提取 | `content_list` | `table_body` + `table_caption` |
| 标题层级识别 | `content_list` | `text_level` (0=N) |
| 公式 LaTeX 提取 | `content_list` | `text` + `text_format: "latex"` |
| 像素级区域提取 | `layout.json` | `para_blocks` → `spans[].bbox` + `spans[].content` |
| 页眉/页脚获取 | `layout.json` | `discarded_blocks[]` |
| 页面尺寸信息 | `layout.json` | `page_size` |
| 跨页表格拼接 | `content_list` | `type: "table"` + `page_idx` |
| 图文关系建立 | `content_list` | `image` 的 `image_caption` + 前/后 `text` 块 |

---

## 4. MVP 测试：必要字段与必传参数

### 4.1 云端 API 完整参数列表

#### 4.1.1 提交任务参数（POST /api/v4/extract/task）

| 参数 | 类型 | 必传 | 默认值 | 说明 |
|---|---|---|---|---|
| **`url`** | `string` | **✅ 是** | — | 待解析文件的公网可访问 URL |
| `is_ocr` | `bool` | 否 | `false` | 是否开启 OCR。扫描件/图片建议 `true` |
| `enable_formula` | `bool` | 否 | `true` | 是否开启公式识别 |
| `enable_table` | `bool` | 否 | `true` | 是否开启表格识别 |
| `language` | `string` | 否 | `"ch"` | 文档语言：`"ch"`（中文）/ `"en"`（英文）/ `"ja"`（日文）等 |
| `model_version` | `string` | 否 | `"pipeline"` | 解析引擎：`"pipeline"`（默认）/ `"vlm"`（推荐高精度）/ `"MinerU-HTML"`（HTML 文件专用） |
| `page_ranges` | `string` | 否 | — | 页码范围。如 `"2,4-6"` 仅解析第 2、4-6 页；`"2--2"` 表示第 2 页到倒数第 2 页 |
| `extra_formats` | `[string]` | 否 | — | 额外导出格式，可选：`"docx"`, `"html"`, `"latex"` |
| `callback` | `string` | 否 | — | 回调 URL（任务完成后 POST 推送结果），支持 HTTP/HTTPS |
| `seed` | `string` | 否 | — | 回调签名密钥。使用 `callback` 时**必填** |
| `no_cache` | `bool` | 否 | `false` | 是否绕过缓存，重新解析 |
| `cache_tolerance` | `int` | 否 | `900` | 缓存容忍时间（秒），默认 15 分钟 |

#### 4.1.2 认证头

| Header | 值 | 是否必传 |
|---|---|---|
| `Content-Type` | `application/json` | **✅ 是** |
| `Authorization` | `Bearer <your-token>` | **✅ 是** |

### 4.2 MVP 测试最小调用

**仅需 1 个必传参数 `url` + 1 个必传 Header `Authorization`**：

```python
import requests
import time

TOKEN = "your-api-token-here"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}

# Step 1: 提交任务（MVP 最小参数）
resp = requests.post(
    "https://mineru.net/api/v4/extract/task",
    headers=HEADERS,
    json={"url": "https://example.com/test.pdf"}
)
task_id = resp.json()["data"]["task_id"]

# Step 2: 轮询直到完成
while True:
    resp = requests.get(
        f"https://mineru.net/api/v4/extract/task/{task_id}",
        headers=HEADERS
    )
    state = resp.json()["data"]["state"]
    if state == "done":
        zip_url = resp.json()["data"]["full_zip_url"]
        break
    elif state == "failed":
        raise Exception(resp.json()["data"].get("err_msg", "Unknown error"))
    time.sleep(3)

# Step 3: 下载并解压结果
import zipfile, io
zip_resp = requests.get(zip_url)
with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
    zf.extractall("./mineru_output")
```

### 4.3 MVP 推荐参数组合

| 场景 | 参数配置 |
|---|---|
| **标准 PDF 文档** | `{"url": "...", "language": "ch", "model_version": "pipeline"}` |
| **扫描件 / 图片型 PDF** | `{"url": "...", "is_ocr": true, "language": "ch"}` |
| **高精度需求** | `{"url": "...", "model_version": "vlm", "enable_formula": true, "enable_table": true}` |
| **含公式和表格的学术论文** | `{"url": "...", "enable_formula": true, "enable_table": true, "language": "ch"}` |
| **DOCX / 办公文档** | `{"url": "...", "enable_formula": false, "enable_table": true}` |
| **指定页码范围** | `{"url": "...", "page_ranges": "1-50"}` |
| **需要额外格式导出** | `{"url": "...", "extra_formats": ["docx", "html"]}` |

### 4.4 MVP 测试完整清单

| 序号 | 准备项 | 说明 |
|---|---|---|
| 1 | **API Token** | 访问 `https://mineru.net` 注册 → 申请 API → 创建 Token |
| 2 | **公网文件 URL** | 待解析文档需托管到公网可访问地址（OSS / 云存储） |
| 3 | **HTTP 客户端** | Python `requests` 库或其他 HTTP 工具 |
| 4 | **磁盘空间** | 预留解压后的输出目录空间 |
| 5 | **文件合规** | ≤ 200MB，≤ 600 页 |

### 4.5 错误处理

| HTTP 状态码 | 含义 | 处理方式 |
|---|---|---|
| `200` + `code: 0` | 成功 | 正常处理 |
| `401` | Token 无效或过期 | 重新申请 Token |
| `422` | 参数校验失败 | 检查请求参数格式 |
| `429` | 请求频率超限 | 降低请求频率后重试 |
| `state: "failed"` | 解析失败 | 检查 `err_msg` 字段，确认文件可访问且未损坏 |

---

## 附录：Python 完整调用示例

```python
"""
MinerU 云端 API MVP 调用脚本
依赖: pip install requests
"""
import io
import os
import time
import zipfile
import requests

# ============ 配置 ============
TOKEN = "your-api-token"               # ← 替换为实际 Token
FILE_URL = "https://example.com/doc.pdf"  # ← 替换为实际文件 URL
OUTPUT_DIR = "./mineru_output"          # 输出目录
POLL_INTERVAL = 3                       # 轮询间隔（秒）
MAX_WAIT = 300                          # 最大等待时间（秒）

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}"
}
BASE_URL = "https://mineru.net/api/v4/extract/task"

def submit_task(file_url: str, **kwargs) -> str:
    """提交解析任务，返回 task_id。"""
    payload = {"url": file_url, **kwargs}
    resp = requests.post(BASE_URL, headers=HEADERS, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if data["code"] != 0:
        raise RuntimeError(f"提交失败: {data.get('msg', 'Unknown')}")
    task_id = data["data"]["task_id"]
    print(f"[提交] task_id = {task_id}")
    return task_id

def poll_until_done(task_id: str, interval: int = 3, max_wait: int = 300) -> str:
    """轮询直到任务完成，返回 zip 下载链接。"""
    url = f"{BASE_URL}/{task_id}"
    elapsed = 0
    while elapsed < max_wait:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()["data"]
        state = data["state"]
        print(f"[轮询] state = {state} ({elapsed}s)")

        if state == "done":
            return data["full_zip_url"]
        if state == "failed":
            raise RuntimeError(f"解析失败: {data.get('err_msg', 'Unknown')}")

        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(f"超时: 等待 {max_wait}s 未完成")

def download_and_extract(zip_url: str, output_dir: str) -> str:
    """下载 ZIP 并解压。"""
    os.makedirs(output_dir, exist_ok=True)
    resp = requests.get(zip_url)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(output_dir)
    files = os.listdir(output_dir)
    print(f"[完成] 输出文件: {files}")
    return output_dir

# ============ 主流程 ============
if __name__ == "__main__":
    task_id = submit_task(
        FILE_URL,
        language="ch",
        enable_formula=True,
        enable_table=True,
        # extra_formats=["docx"],  # 如需额外格式取消注释
    )
    zip_url = poll_until_done(task_id, POLL_INTERVAL, MAX_WAIT)
    output = download_and_extract(zip_url, OUTPUT_DIR)
    print(f"输出目录: {os.path.abspath(output)}")
```
