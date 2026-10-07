# MinerU MVP 测试配置指南 v1.0

> **版本**: v1.0 | **日期**: 2026-05-24 | **状态**: ✅ 本地执行已验证
>
> 本文档整合了 MinerU 云端 API 官方文档 (https://mineru.net/apiManage/docs)、
> 本地 MVP 测试项目代码 (`mineru-mvp-test/`)，以及 **2026-05-24 实际 API 调用结果**。
> 凡标注 **[实测]** 的章节均基于本地实际输出，与官方文档存在差异处以本地实测为准。

---

## 目录

1. [MinerU Pipeline 执行思路与代码路径](#1-mineru-pipeline-执行思路与代码路径)
2. [支持的输入文件格式](#2-支持的输入文件格式)
3. [关键参数规范详解](#3-关键参数规范详解)
4. [API 调用流程与响应规范](#4-api-调用流程与响应规范)
5. [输出文件格式规范](#5-输出文件格式规范)
6. [布局信息详解](#6-布局信息详解)
7. [MVP 测试环境配置](#7-mvp-测试环境配置)
8. [本地运行步骤与预期结果](#8-本地运行步骤与预期结果)
9. [官方文档与本地输出对比校验](#9-官方文档与本地输出对比校验)

---

## 1. MinerU Pipeline 执行思路与代码路径

### 1.1 整体执行流程

```
┌──────────────────────────────────────────────────────────────────┐
│                    MinerU MVP Pipeline 完整流程                    │
│                                                                  │
│  [1] 环境准备                                                    │
│      ├─ pip install -r requirements.txt                          │
│      ├─ 配置 .env (Token / 参数)                                  │
│      └─ 生成 sample.pdf (python generate_sample_pdf.py)           │
│                           ↓                                      │
│  [2] 文件就绪                                                    │
│      ├─ 若 FILE_URL 已设置 → 直接使用公网 URL                      │
│      └─ 否则 → 上传本地 PDF 至临时托管 (file.io / transfer.sh)     │
│                           ↓                                      │
│  [3] POST /api/v4/extract/task  提交解析任务                      │
│      └─ 请求体: {"url": "...", "language": "ch", ...}            │
│      └─ 响应:   {"data": {"task_id": "..."}}                     │
│                           ↓                                      │
│  [4] GET  /api/v4/extract/task/{task_id}  轮询任务状态            │
│      └─ 每 3s 查询一次，直到 state = "done" 或 "failed"          │
│      └─ state 流转: pending → running → converting → done        │
│                           ↓                                      │
│  [5] state=done → 获取 full_zip_url → 下载 ZIP 包                 │
│      └─ 解压到 output/{task_id[:8]}/                             │
│                           ↓                                      │
│  [6] 打印结果摘要                                                │
│      └─ 文件清单 + content_list 元素类型统计                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 测试脚本存放路径

| 文件 | 路径 | 说明 |
|---|---|---|
| **主 Pipeline 脚本** | `../mineru-mvp-test/run_mvp.py` | 完整的 MVP 测试入口 |
| **PDF 生成脚本** | `../mineru-mvp-test/generate_sample_pdf.py` | 生成中英文混排示例 PDF |
| **环境变量配置** | `../mineru-mvp-test/.env` | Token + 解析参数 |
| **配置模板** | `../mineru-mvp-test/.env.example` | 不含敏感信息的模板 |
| **示例 PDF** | `../mineru-mvp-test/sample.pdf` | 2 页中英文混排 PDF |
| **README** | `../mineru-mvp-test/README.md` | 运行说明 |

> 以上路径均相对于 `docs/` 目录。绝对路径根目录为 `D:\graghRAG-agent\`。

### 1.3 关键代码模块说明

`run_mvp.py` 由以下模块组成：

| 函数 | 行号 | 职责 |
|---|---|---|
| `load_config()` | L34-62 | 从 `.env` 加载所有配置项，校验 Token 必填 |
| `upload_to_file_io()` | L69-85 | 上传 PDF 至 file.io 获取公网 URL |
| `upload_to_transfer_sh()` | L88-107 | 上传 PDF 至 transfer.sh（备用） |
| `upload_local_file()` | L110-130 | 串联上传策略，全部失败则提示手动方案 |
| `resolve_file_url()` | L133-142 | 优先级: `FILE_URL` > 本地上传 |
| `MinerUClient.submit()` | L161-179 | 构造请求体并 POST 提交任务 |
| `MinerUClient.poll()` | L181-214 | 轮询任务状态，带进度条输出 |
| `download_and_extract()` | L221-248 | 流式下载 ZIP 并解压 |
| `print_results_summary()` | L251-311 | 打印文件清单 + content_list 类型统计 |

---

## 2. 支持的输入文件格式

### 2.1 云端 API 支持格式

| 格式 | 扩展名 | 支持状态 | 说明 |
|---|---|---|---|
| **PDF** | `.pdf` | ✅ | 核心格式；扫描版自动 OCR |
| **Word** | `.docx` | ✅ (v1.0+) | 原生解析 XML 结构 |
| **Word** | `.doc` | ✅ | 旧版格式 |
| **PowerPoint** | `.pptx` | ✅ (v3.x) | 原生解析 |
| **PowerPoint** | `.ppt` | ✅ | 旧版需先转 PDF |
| **Excel** | `.xlsx` | ✅ (v3.x) | 表格解析 |
| **图片** | `.png`, `.jpg`, `.jpeg` | ✅ | 直接图片输入 |
| **HTML 网页** | `.html` | ✅ | 网页内容提取 |
| **EPUB** | `.epub` | ✅ | 电子书格式 |

### 2.2 云端 API 限制

| 限制项 | 数值 |
|---|---|
| 单文件大小上限 | ≤ 200 MB |
| 单文件页数上限 | ≤ 600 页 |
| 免费额度 | 每日 2000 页高优先级 |
| 文件云端有效期 | 30 天 |
| 文件传入方式 | **仅公网 URL**，不支持直接上传 |

### 2.3 本地测试文件

本次 MVP 测试使用的示例 PDF 由 `generate_sample_pdf.py` 生成：

| 属性 | 值 |
|---|---|
| 文件名 | `sample.pdf` |
| 页数 | 2 页 |
| 内容类型 | 中英文标题、正文段落、表格 (含数值)、公式 |
| 字体 | Windows: 楷体 (simkai) + 黑体 (simhei)；非 Windows: 回退纯英文 Helvetica |
| 文件大小 | ~60 KB |

---

## 3. 关键参数规范详解

### 3.1 提交任务请求体参数（POST /api/v4/extract/task）

| 参数 | 类型 | 必传 | 默认值 | 取值范围 | 说明 |
|---|---|---|---|---|---|
| **`url`** | `string` | **✅ 是** | — | 公网可访问的 HTTP/HTTPS URL | 待解析文件的网络地址。不支持直接文件上传 |
| `is_ocr` | `bool` | 否 | `false` | `true` / `false` | 是否启用 OCR。扫描件、图片型 PDF 必须设为 `true`；文字型 PDF 设为 `false` 可提速 |
| `enable_formula` | `bool` | 否 | `true` | `true` / `false` | 是否识别公式并转 LaTeX。含公式的学术论文应开启；纯文本/表格文档可关闭以提速 |
| `enable_table` | `bool` | 否 | `true` | `true` / `false` | 是否识别表格并转 HTML。关闭可将纯文本文档的解析提速 30-50% |
| `language` | `string` | 否 | `"ch"` | `"ch"` / `"en"` / `"ja"` / 其他 | 文档主体语言。影响 OCR 语言模型和分句策略 |
| `model_version` | `string` | 否 | `"pipeline"` | `"pipeline"` / `"vlm"` / `"MinerU-HTML"` | 解析引擎选择（见下方详细说明） |
| `page_ranges` | `string` | 否 | — | 如 `"2,4-6"` 或 `"1--2"` | 指定解析的页码范围。"2--2" 表示第2页到倒数第2页 |
| `extra_formats` | `[string]` | 否 | — | `"docx"` / `"html"` / `"latex"` | 额外导出格式。ZIP 包中会增加对应格式文件 |
| `callback` | `string` | 否 | — | HTTP/HTTPS URL | 回调地址。任务完成后 POST 推送结果，替代轮询 |
| `seed` | `string` | 条件必传 | — | 任意字符串 | 回调签名密钥。使用 `callback` 时**必传** |
| `no_cache` | `bool` | 否 | `false` | `true` / `false` | 是否跳过缓存强制重新解析 |
| `cache_tolerance` | `int` | 否 | `900` | 整数 (秒) | 缓存容忍时间。默认 15 分钟内相同请求返回缓存 |

### 3.2 model_version 参数详解

| 取值 | 适用场景 | 精度 | 速度 | 说明 |
|---|---|---|---|---|
| `"pipeline"` | 标准 PDF 文档 | 高 | 快 | 默认引擎，CPU 友好，适合大多数文档 |
| `"vlm"` | 复杂排版 / 高精度需求 | 更高 | 较慢 | 视觉语言模型，支持更多 BlockType，页眉页脚以独立类型输出 |
| `"MinerU-HTML"` | HTML 文件输入 | — | — | HTML 文件专用解析引擎 |

### 3.3 认证请求头

| Header | 值 | 必传 | 说明 |
|---|---|---|---|
| `Content-Type` | `application/json` | **✅ 是** | 请求体格式声明 |
| `Authorization` | `Bearer {token}` | **✅ 是** | JWT Token 认证 |

### 3.4 本地 .env 参数映射

`run_mvp.py` 通过以下映射关系读取 `.env` → 构造 API 请求体：

```python
# .env 变量                    → API 请求体参数
MINERU_API_TOKEN               → Authorization: Bearer {token}
MINERU_API_BASE_URL            → 请求目标 URL
FILE_URL                       → url (优先)
LOCAL_PDF_PATH                 → 自动上传后获得 url (备选)
LANGUAGE                       → language
IS_OCR                         → is_ocr
ENABLE_FORMULA                 → enable_formula
ENABLE_TABLE                   → enable_table
MODEL_VERSION                  → model_version
MAX_WAIT_SECONDS               → 轮询超时时间
POLL_INTERVAL_SECONDS          → 轮询间隔
OUTPUT_DIR                     → 本地输出目录
```

### 3.5 参数推荐组合

| 场景 | 参数 |
|---|---|
| **MVP 最小测试** | `{"url": "<公网URL>"}` |
| **中文 PDF 文档** | `{"url": "...", "language": "ch", "model_version": "pipeline"}` |
| **扫描件** | `{"url": "...", "is_ocr": true, "language": "ch"}` |
| **学术论文** | `{"url": "...", "enable_formula": true, "enable_table": true, "language": "ch"}` |
| **高精度解析** | `{"url": "...", "model_version": "vlm"}` |
| **指定页码范围** | `{"url": "...", "page_ranges": "1-50"}` |
| **需额外格式** | `{"url": "...", "extra_formats": ["docx", "html"]}` |
| **回调模式** | `{"url": "...", "callback": "https://your-server.com/hook", "seed": "secret"}` |

---

## 4. API 调用流程与响应规范

### 4.1 基础信息

| 项目 | 值 |
|---|---|
| API 基础 URL | `https://mineru.net/api/v4/extract/task` |
| 请求方式 (提交) | `POST` |
| 请求方式 (查询) | `GET` |
| Content-Type | `application/json` |
| 认证方式 | `Authorization: Bearer {token}` |
| 调用模式 | 异步 (提交 → 轮询 → 下载) |

### 4.2 状态流转

```
                    提交任务
                       │
                       ▼
                  ┌─────────┐
                  │ pending │  排队中
                  └────┬────┘
                       │
                       ▼
                  ┌─────────┐
                  │ running │  正在解析 (含 extract_progress)
                  └────┬────┘
                       │
                       ▼
                  ┌───────────┐
                  │ converting │  格式转换中
                  └─────┬─────┘
                        │
                   ┌────┴────┐
                   ▼         ▼
              ┌──────┐  ┌────────┐
              │ done │  │ failed │
              └──────┘  └────────┘
               成功       失败 (含 err_msg)
```

### 4.3 响应 JSON 结构

#### 提交任务响应

```json
{
    "code": 0,
    "data": { "task_id": "a90e6ab6-44f3-4554-b459-b62fe4c6b436" },
    "msg": "ok",
    "trace_id": "c876cd60b202f2396de1f9e39a1b0172"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | `int` | 状态码：`0` = 成功，非 `0` = 失败 |
| `data.task_id` | `string` | 任务唯一标识 (UUID)，用于后续轮询 |
| `msg` | `string` | 状态消息 |
| `trace_id` | `string` | 请求追踪 ID |

#### 轮询进行中响应

```json
{
    "code": 0,
    "data": {
        "task_id": "47726b6e-...",
        "state": "running",
        "err_msg": "",
        "extract_progress": {
            "extracted_pages": 1,
            "total_pages": 2,
            "start_time": "2025-01-20 11:43:20"
        }
    },
    "msg": "ok"
}
```

#### 任务完成响应

```json
{
    "code": 0,
    "data": {
        "task_id": "47726b6e-...",
        "state": "done",
        "full_zip_url": "https://cdn-mineru.openxlab.org.cn/pdf/018e53ad-....zip",
        "err_msg": ""
    },
    "msg": "ok"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.state` | `string` | 任务当前状态 |
| `data.full_zip_url` | `string` | 解析结果 ZIP 下载链接 |
| `data.err_msg` | `string` | 错误信息（失败时非空） |
| `data.extract_progress` | `object` | 解析进度（进行中时存在） |

---

## 5. 输出文件格式规范

### 5.1 ZIP 包文件清单 **[实测更新]**

本次 MVP 使用 `model_version=pipeline` 解析 15 页 arXiv 论文 PDF，ZIP 包解压后包含 **7 个文件/目录**：

| 编号 | 文件名 | 格式 | 大小 | 说明 |
|---|---|---|---|---|
| 1 | `full.md` | `.md` | 44 KB | 完整 Markdown 解析结果 |
| 2 | `{uuid}_content_list.json` | `.json` | 72 KB | 按阅读顺序平铺的内容列表 (141 项, 11 种类型) |
| 3 | `{uuid}_content_list_v2.json` | `.json` | 128 KB | 按页分组的新版内容列表 (414 项, 13 种类型) |
| 4 | `{uuid}_model.json` | `.json` | 228 KB | 模型推理原始输出 |
| 5 | `layout.json` | `.json` | 1.1 MB | 按页组织的块级布局信息 (15 页) |
| 6 | `{uuid}_origin.pdf` | `.pdf` | 2.1 MB | 原始输入 PDF |
| 7 | `images/` | 目录 | 776 KB | 提取的 14 张图片 (公式/表格/图表截图) |

> **[实测] 与官方文档的关键差异**：
> 1. ZIP 含 **7 项**（非官方文档的 4 个文件）：增加了 `_v2.json`、`_origin.pdf`、`images/`
> 2. `layout.json` 文件名**不带 UUID 前缀**，直接命名为 `layout.json`
> 3. 文件命名使用 UUID（非 `task_id`），如 `185f605f-00bf-4f6f-933b-00f58332e212_content_list.json`
> 4. `_content_list_v2.json` 格式为**按页分组的嵌套结构**，与 v1 的平铺列表不同

### 5.2 full.md — Markdown 输出

- 保留标题层级 (`#`, `##`, `###`)
- 表格转换为 Markdown 表格语法
- 公式保留 LaTeX 语法（行间 `$$...$$`，行内 `$...$`）
- 图片以引用路径形式呈现
- 按阅读顺序组织内容

### 5.3 *_content_list.json (v1) — 内容列表 **[实测]**

平铺结构，141 个元素，所有 `bbox` 坐标统一为 **0-1000 归一化**。

**本次实测元素类型分布：**

| type | 数量 | 说明 |
|---|---|---|
| `text` | 103 | 正文段落/作者信息/标题，含 `text_level` 分层级 |
| `page_number` | 14 | 页码（每页一个） |
| `equation` | 5 | 行间公式，含 LaTeX 字符串 |
| `page_footnote` | 5 | 页脚注释 |
| `table` | 4 | 表格，含 HTML `table_body` |
| `list` | 3 | 列表项 |
| `image` | 3 | 图片块，含 `image_caption` |
| `chart` | 2 | 图表块 |
| `footer` | 1 | 页脚文本 |
| `aside_text` | 1 | 侧边文本/边注 |

**实测发现的新类型** (官方文档未提及)：`page_number`、`chart`、`aside_text`。

#### v1 各类型字段对照

| type | 特有字段 | 通用字段 |
|---|---|---|
| `text` | `text` (文本), `text_level` (1/2) | `type`, `bbox`, `page_idx` |
| `page_number` | `text` (页码) | `type`, `bbox`, `page_idx` |
| `equation` | `text` (LaTeX), `text_format` ("latex"), `img_path` | `type`, `bbox`, `page_idx` |
| `table` | `table_body` (HTML), `table_caption`, `table_footnote`, `img_path` | `type`, `bbox`, `page_idx` |
| `image` | `img_path`, `image_caption` | `type`, `bbox`, `page_idx` |
| `chart` | `img_path`, `chart_body`, `chart_caption` | `type`, `bbox`, `page_idx` |
| `footer` / `page_footnote` / `aside_text` | `text` | `type`, `bbox`, `page_idx` |

### 5.3.1 *_content_list_v2.json (v2) — 新版内容列表 **[实测]**

按页分组的嵌套结构，414 个元素，13 种类型。

**v2 结构**：`[ [page0_items], [page1_items], ... ]` — 外层数组按页索引。

**v2 新增类型与结构：**

| v2 类型 | 数量 | v1 对应 | 说明 |
|---|---|---|---|
| `text` | 217 | `text` | 嵌套在 `paragraph` 的 `content.paragraph_content[]` 中 |
| `paragraph` | 78 | — | v2 特有，作为文本容器 |
| `equation_inline` | 56 | — | v2 特有，行内公式（v1 无此粒度） |
| `title` | 25 | `text`+`text_level` | v2 标题独立类型 |
| `page_number` | 14 | `page_number` | — |
| `page_footnote` | 5 | `page_footnote` | — |
| `equation_interline` | 5 | `equation` | v2 行间公式独立类型 |
| `table` | 4 | `table` | — |
| `list` | 3 | `list` | — |
| `image` | 3 | `image` | — |
| `chart` | 2 | `chart` | — |
| `page_footer` | 1 | `footer` | v2 命名差异 |
| `page_aside_text` | 1 | `aside_text` | v2 命名差异 |

> **v2 vs v1 关键变化**：按页分组、`text` 嵌套到 `paragraph.content.paragraph_content`、新增 `equation_inline`/`equation_interline` 细粒度类型、`title` 取代 `text_level`。

### 5.4 layout.json — 布局中间结果 **[实测]**

顶层结构：`{"pdf_info": [ {page_data}, ... ]}`，共 15 页。

**实测顶层字段：**
- `pdf_info` — 按页组织的数组
- 每页包含：`preproc_blocks` (预处理块数组)、`page_size`、`page_idx`

> **[实测] 与官方文档差异**：实际字段为 `preproc_blocks`（非 `para_blocks` 和 `discarded_blocks`），无 `_backend` 顶层字段。

**嵌套层级**：`page → preproc_blocks[i] → lines[k] → spans[m]`

**本次实测 BlockType 分布 (18 种, 共 ~1440 块)：**

| BlockType | 数量 | 说明 |
|---|---|---|
| `text` | 1163 | 正文内容 |
| `inline_equation` | 110 | 行内公式 |
| `ref_text` | 80 | 参考文献文本 |
| `title` | 50 | 标题 |
| `interline_equation` | 20 | 行间公式 |
| `table` | 16 | 表格 |
| `page_number` | 14 | 页码 |
| `image` | 12 | 图片 |
| `table_caption` | 8 | 表格标题 |
| `table_body` | 8 | 表格主体 |
| `chart` | 8 | 图表 |
| `image_caption` | 6 | 图片标题 |
| `image_body` | 6 | 图片主体 |
| `chart_caption` | 6 | 图表标题 |
| `chart_body` | 4 | 图表主体 |
| `page_footnote` | 5 | 页脚注释 |
| `abstract` | 2 | 摘要 |
| `footer` | 1 | 页脚文本 |
| `aside_text` | 1 | 侧边文本 |

> **[实测] 与官方文档的 BlockType 差异**：
> 1. `inline_equation`、`ref_text` 为文档未提及的新类型
> 2. `table`/`image`/`chart` 被拆分为 `_body` + `_caption` 子类型
> 3. 未发现 `discarded_blocks` 字段，`header`/`footer`/`page_number` 直接包含在 `preproc_blocks` 中
> 4. 无 `doc_title`、`list`、`code`、`algorithm` 类型 (pipeline 后端正常)

**Span 级别字段 (实测)**：

| Span 类型 | 内容字段 |
|---|---|
| `text` | `content` (文本), `score` (置信度) |
| `inline_equation` | `content` (LaTeX) |
| `interline_equation` | `content` (LaTeX) |
| `table` | `html` (表格 HTML) |
| `image` | `image_path` |

### 5.5 *_model.json — 模型原始输出

模型推理的原始响应数据，用于调试和高级分析场景。

---

## 6. 布局信息详解

### 6.1 坐标系统

| 后端 | bbox 坐标空间 | 原点 |
|---|---|---|
| `pipeline` | 原始像素值 | 页面左上角 (0, 0) |
| `vlm` / `hybrid` | 0-1000 归一化 | 页面左上角 (0, 0) |

**bbox 格式**：`[x0, y0, x1, y1]`
- `x0` 左边界 / `y0` 上边界 / `x1` 右边界 / `y1` 下边界

### 6.2 坐标归一化转换

```python
page_w, page_h = page["page_size"]
norm_x0 = pixel_x0 / page_w * 1000
norm_y0 = pixel_y0 / page_h * 1000
```

### 6.3 布局信息在数值提取中的应用

| 提取场景 | 推荐数据源 | 字段 |
|---|---|---|
| 表格数值 | `content_list` | `table_body` + `table_caption` |
| 标题层级 | `content_list` | `text_level` (0=正文, 1=一级标题, ...) |
| LaTeX 公式 | `content_list` | `text` + `text_format: "latex"` |
| 像素级精确定位 | `layout.json` | `para_blocks` → `spans[].bbox` + `spans[].content` |
| 页眉/页脚 | `layout.json` | `discarded_blocks[]` |
| 跨页表格 | `content_list` | `type: "table"` + `page_idx` |

---

## 7. MVP 测试环境配置

### 7.1 项目文件结构

```
D:\graghRAG-agent\
├── mineru-mvp-test/                  ← MVP 测试项目根目录
│   ├── .venv/                        ← uv 虚拟环境（独立隔离）
│   ├── .env                          ← 环境变量 (Token + 参数)
│   ├── .env.example                  ← 配置模板
│   ├── .gitignore                    ← 排除 .venv/ .env output/
│   ├── CLAUDE.md                     ← 项目规范说明（含环境隔离规则）
│   ├── requirements.txt              ← Python 依赖
│   ├── generate_sample_pdf.py        ← 示例 PDF 生成
│   ├── run_mvp.py                    ← ★ MVP Pipeline 主入口
│   ├── sample.pdf                    ← 已生成的示例 PDF
│   ├── output/                       ← 解析结果输出
│   └── README.md                     ← 运行说明
└── docs/
    ├── MinerU-API-Specification.md   ← MinerU API 详细规范
    ├── MinerU_MVP测试配置指南.md_v1.0.md  ← 本文档
    └── LangExtract-Pipeline-Specification.md
```

> **环境隔离说明**：MinerU (`mineru-mvp-test/.venv`) 与 LangExtract (`langextract/.venv`)
> 使用各自独立的虚拟环境，避免包版本冲突造成环境污染。

### 7.2 前置依赖

```bash
pip install -r requirements.txt
```

依赖清单：`requests>=2.25.0`, `python-dotenv>=0.19.0`, `fpdf2>=2.7.0`

### 7.3 Token 配置

Token 已预置在 `.env` 文件中，格式为 JWT Token。

- **获取流程**: `https://mineru.net` → 注册/登录 → API 管理 → 申请 API → 创建 Token
- **有效期**: 见 token payload 的 `exp` 字段
- **认证方式**: HTTP Header `Authorization: Bearer {token}`

### 7.4 文件上传策略

MinerU 云端 API 仅接受**公网 URL**作为文件来源。MVP 测试项目采用三层策略：

```
优先级 1: .env 中 FILE_URL 已设置 → 直接使用
          (手动上传至 OSS/COS/GitHub Raw)
优先级 2: 自动上传 → file.io → 获取公网 URL
优先级 3: 自动上传 → transfer.sh → 获取公网 URL
          (优先级 2 失败时)
全部失败 → 打印错误提示，建议手动方案
```

---

## 8. 本地运行步骤与预期结果

### 8.1 运行前准备：激活虚拟环境 **[强制]**

为避免与 LangExtract 等其他组件发生依赖冲突，MinerU MVP 使用 `uv` 管理独立虚拟环境。
**所有 MinerU 操作必须先激活此环境。**

```bash
# 进入项目目录
cd D:/graghRAG-agent/mineru-mvp-test

# 激活虚拟环境 (Git Bash / WSL)
source .venv/Scripts/activate

# 验证环境已激活
python -c "import sys; print(sys.prefix)"
# 预期输出: D:\graghRAG-agent\mineru-mvp-test\.venv
```

> **注意事项**：
> - 每次新终端窗口执行 MinerU 操作前，都需重新激活 `.venv`
> - 克隆项目后首次使用，执行 `uv venv .venv --python 3.12 && source .venv/Scripts/activate && uv pip install -r requirements.txt` 初始化
> - 禁止在全局 Python 环境中安装 MinerU MVP 的依赖

### 8.2 运行阶段

```bash
# Step 0: 激活虚拟环境（强制）
source .venv/Scripts/activate

# Step 1: 安装依赖（首次）
uv pip install -r requirements.txt

# Step 2: 生成示例 PDF (如已存在可跳过)
python generate_sample_pdf.py
# 预期输出:
# [字体] Regular: simkai.ttf
# [字体] Bold:    simhei.ttf
# [生成] 示例 PDF 已保存: sample.pdf (2 页)

# Step 3: 确认 .env 配置
# 检查 MINERU_API_TOKEN 已配置 (已预置)
# 确认 FILE_URL 为空 (将自动上传) 或已填入公网 URL

# Step 4: 运行 MVP Pipeline
python run_mvp.py
```

### 8.2 预期控制台输出

```
============================================================
  MinerU 云端 API — MVP 测试 Pipeline
  启动时间: 2026-05-24 15:30:00
============================================================

[配置] API 地址: https://mineru.net/api/v4/extract/task
[配置] 语言: ch, OCR: false, 公式: true, 表格: true
[文件] 使用本地文件: D:\graghRAG-agent\mineru-mvp-test\sample.pdf
[上传] 正在上传到 file.io ...
[上传] 成功: https://file.io/xxxxxxxxxxxx

[提交] 正在提交解析任务...
   URL: https://file.io/xxxxxxxxxxxx
   参数: {"language": "ch", "is_ocr": false, ...}
   task_id: a90e6ab6-44f3-4554-b459-b62fe4c6b436

[轮询] 等待任务完成 (最多 300s)...
   [running] ==========> 18s | Pages: 1/2
   [done] ==================> 25s | Pages: 2/2

[下载] 正在下载结果 ZIP ...
   [====================] 100%

[解压] 完成 → D:\graghRAG-agent\mineru-mvp-test\output\a90e6ab6

============================================================
  解析结果摘要
============================================================

  输出目录: D:\graghRAG-agent\mineru-mvp-test\output\a90e6ab6
  文件数量: 4

  文件清单:
    {task_id}_content_list.json           X.X KB  ← 内容列表
    {task_id}_layout.json                 X.X KB  ← 布局中间结果
    {task_id}_model.json                  X.X KB  ← 模型原始输出
    full.md                               X.X KB  ← Markdown 输出

  统计:
    Markdown 文件: 1
    JSON 文件:     3

  Content List 元素统计:
    [T] text            XX  个
    [B] table           XX  个
    [E] equation        XX  个

============================================================

[完成] 总耗时: XX.Xs
[完成] 输出目录: D:\graghRAG-agent\mineru-mvp-test\output\{task_id_prefix}
```

### 8.3 错误处理速查

| 错误现象 | 可能原因 | 解决方案 |
|---|---|---|
| `.env 文件未找到` | 未从 `.env.example` 复制 | `cp .env.example .env` |
| `MINERU_API_TOKEN 未设置` | Token 未配置 | 在 `.env` 中填入有效 Token |
| `本地文件不存在` | sample.pdf 未生成 | `python generate_sample_pdf.py` |
| `所有上传服务均失败` | 网络不通 | 手动上传至云存储，设置 `FILE_URL` |
| HTTP `401` | Token 无效/过期 | 重新申请 Token |
| HTTP `422` | 参数格式错误 | 检查请求体 JSON 格式 |
| `state: failed` | 文件损坏/不可访问 | 检查 `err_msg`，确认文件 URL 可公网访问 |
| 轮询超时 | 文件过大/API 繁忙 | 增大 `MAX_WAIT_SECONDS` 或检查文件 ≤200MB |

---

## 9. 官方文档与本地输出对比校验 **[已完成]**

### 9.1 校验信息

| 项目 | 值 |
|---|---|
| 测试时间 | 2026-05-24 15:35 CST |
| task_id | `87bc1f56-84d5-4cf9-9fdf-9190e785701f` |
| 输入文件 | arXiv 1706.03762v7 (15 页 PDF) |
| 模型 | pipeline |
| 总耗时 | ~10s (提交→完成) |
| 结果路径 | `mineru-mvp-test/output/87bc1f56/` |

### 9.2 输出文件对比

| 对比项 | 官方文档描述 | 本地实测结果 | 是否一致 |
|---|---|---|---|
| ZIP 包含文件数 | 4 个 | **7 个/目录** | ❌ **不一致** |
| `full.md` 存在 | ✅ | ✅ (44 KB) | ✅ |
| `*_content_list.json` 存在 | ✅ | ✅ (72 KB, 141 项) | ✅ |
| `*_content_list_v2.json` 存在 | 未提及 | ✅ (128 KB, 414 项) | ❌ **新增** |
| `*_layout.json` 存在 | ✅ | ✅ (1.1 MB, `layout.json`) | ⚠️ 命名不同 |
| `*_model.json` 存在 | ✅ | ✅ (228 KB) | ✅ |
| `*_origin.pdf` 存在 | 未提及 | ✅ (2.1 MB) | ❌ **新增** |
| `images/` 目录存在 | 未提及 | ✅ (14 张, 776 KB) | ❌ **新增** |

### 9.3 Content List 类型对比

| type | 官方文档 | 本地实测 (v1) | 本地实测 (v2) |
|---|---|---|---|
| `text` | ✅ | 103 项 | 217 项 (嵌套于 paragraph) |
| `table` | ✅ | 4 项 | 4 项 |
| `equation` | ✅ | 5 项 | — (拆分为 interline/inline) |
| `equation_inline` | ❌ 未提及 | — | 56 项 |
| `equation_interline` | ❌ 未提及 | — | 5 项 |
| `image` | ✅ | 3 项 | 3 项 |
| `list` | VLM 后端 | 3 项 | 3 项 |
| `header` | VLM 后端 | — | — |
| `footer` | ✅ | 1 项 | — (重命名为 page_footer) |
| `code` | VLM 后端 | — | — |
| `page_number` | ❌ 未提及 | **14 项** | **14 项** |
| `page_footnote` | ❌ 未提及 | **5 项** | **5 项** |
| `chart` | ❌ 未提及 | **2 项** | **2 项** |
| `aside_text` | ❌ 未提及 | **1 项** | — (重命名为 page_aside_text) |
| `paragraph` | ❌ 未提及 | — | 78 项 (v2 特有容器) |
| `title` | ❌ 未提及 | — | 25 项 (v2 独有) |

### 9.4 layout.json 结构对比

| 对比项 | 官方文档描述 | 本地实测结果 | 是否一致 |
|---|---|---|---|
| 顶层 key | `_backend`, `pdf_info` | 仅 `pdf_info` | ❌ 无 `_backend` |
| 块数组字段名 | `para_blocks` | **`preproc_blocks`** | ❌ **命名不同** |
| `discarded_blocks` | ✅ 存在 | ❌ 不存在 | ❌ |
| 嵌套层级 | page → blocks → lines → spans | page → **preproc_blocks → lines → spans** | ⚠️ 少一层 |
| BlockType 数量 | ~13 种 | **18 种** | ❌ **更多** |
| 新增类型 | — | `inline_equation`, `ref_text`, `table_body`, `table_caption`, `image_body`, `image_caption`, `chart`, `chart_body`, `chart_caption` | ❌ |
| 拆分类型 | `table`, `image` 为单一类型 | `table`/`image`/`chart` 拆为 `_body` + `_caption` | ❌ |
| 坐标系统 | Pipeline 原始像素 | ✅ 原始像素 | ✅ |

### 9.5 响应结构对比

| 对比项 | 官方文档 | 本地实测 | 是否一致 |
|---|---|---|---|
| 提交响应含 `task_id` | ✅ | ✅ | ✅ |
| `trace_id` 存在 | ✅ | ✅ | ✅ |
| 轮询响应含 `state` | ✅ | ✅ | ✅ |
| `extract_progress` 存在 | ✅ | ✅ (含 extracted_pages / total_pages) | ✅ |
| 完成响应含 `full_zip_url` | ✅ | ✅ (cdn-mineru.openxlab.org.cn) | ✅ |
| `err_msg` 存在 | ✅ | ✅ (完成时为空字符串) | ✅ |
| 错误码 `code` | ✅ | ✅ | ✅ |

### 9.6 差异总结与文档更新

**以本地实测为准，以下为与官方文档的关键差异**：

1. **ZIP 包多了 3 项**：`*_content_list_v2.json` (新版)、`*_origin.pdf` (原文件)、`images/` (提取图片)
2. **文件命名**：使用 UUID 非 task_id；`layout.json` 不带前缀
3. **content_list 新增类型**：`page_number`、`chart`、`aside_text`、`page_footnote`；v2 中 `text` 嵌套于 `paragraph` 内
4. **layout.json 结构**：`para_blocks` → `preproc_blocks`；无 `discarded_blocks`；无 `_backend` 字段；块拆分为 body+caption 子类型
5. **BlockType 更多**：18 种 vs 官方 ~13 种，新增 `inline_equation`、`ref_text` 及各类 body/caption 拆分
6. **pipeline 后端也输出 header/footer**：与官方描述 "Pipeline 归入 discarded_blocks" 矛盾

---

## 附录 A：参考链接

- MinerU 官方 API 文档: https://mineru.net/apiManage/docs
- MinerU 官方文档: https://mineru.net/doc/docs/
- MinerU GitHub: https://github.com/opendatalab/MinerU
- MinerU API 讨论: https://github.com/opendatalab/MinerU/discussions/3562
- MinerU 输出文件参考: https://opendatalab.github.io/MinerU/reference/output_files/

## 附录 B：文档修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| v1.0 | 2026-05-24 | 本地实测验证完成：实际调用 MinerU API 解析 15 页 arXiv 论文，对比官方文档发现 6 项关键差异，更新全部输出文件清单、类型枚举、布局结构 |
| *(next)* | — | 待补充：使用 VLM 后端对比测试、本地 sample.pdf 上传测试 |
