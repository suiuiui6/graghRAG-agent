# MinerU MVP 测试

基于 MinerU 云端 API 的文档解析 MVP 测试项目。

## 项目结构

```
mineru-mvp-test/
├── .env                        # 环境变量配置（含 Token）
├── .env.example                # 配置模板
├── requirements.txt            # Python 依赖
├── generate_sample_pdf.py      # 生成示例 PDF
├── run_mvp.py                  # MVP 测试主 Pipeline
├── sample.pdf                  # 示例 PDF（由 generate_sample_pdf.py 生成）
├── output/                     # 解析结果输出目录
└── README.md                   # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
cd mineru-mvp-test
pip install -r requirements.txt
```

### 2. 生成示例 PDF

```bash
python generate_sample_pdf.py
```

输出示例：
```
[生成] 示例 PDF 已保存: sample.pdf (2 页)
```

示例 PDF 包含：中英文文本、表格（含数值数据）、公式、多级标题。

### 3. 配置环境变量

`.env` 文件已包含有效的 API Token，可直接使用。如需调整参数：

```bash
# 编辑 .env
# 关键配置项:
#   MINERU_API_TOKEN    — MinerU API Token（已配置）
#   FILE_URL            — 公网文件 URL（若已手动上传）
#   LOCAL_PDF_PATH      — 本地 PDF 路径（默认 ./sample.pdf）
#   LANGUAGE            — 文档语言 (ch/en/ja)
#   MODEL_VERSION       — 解析引擎 (pipeline/vlm)
```

### 4. 执行 MVP Pipeline

```bash
python run_mvp.py
```

**Pipeline 执行流程：**

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  [1] 加载 .env 配置                                     │
│       ↓                                                 │
│  [2] 确定文件来源                                       │
│       ├─ FILE_URL 已设置 → 直接使用                      │
│       └─ 否则 → 上传本地 PDF 至临时托管 → 获取公网 URL   │
│       ↓                                                 │
│  [3] POST /api/v4/extract/task 提交解析任务              │
│       ↓                                                 │
│  [4] GET  /api/v4/extract/task/{id} 轮询任务状态         │
│       ↓                                                 │
│  [5] state=done → 下载 full_zip_url → 解压到 output/    │
│       ↓                                                 │
│  [6] 打印结果摘要                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 关于文件上传

MinerU 云端 API 要求文件托管在**公网可访问的 URL**。本项目提供两种方式：

### 方式 A：手动上传（推荐）

将 PDF 上传至你的云存储（阿里云 OSS / 腾讯云 COS / GitHub Raw 等），在 `.env` 中设置：

```bash
FILE_URL=https://your-bucket.oss-cn-hangzhou.aliyuncs.com/sample.pdf
```

设置后 Pipeline 会跳过自动上传步骤，直接使用该 URL。

### 方式 B：自动上传

Pipeline 会依次尝试以下免费托管服务上传本地文件：

1. **file.io** — 文件保留至下载一次后删除
2. **transfer.sh** — 14 天有效

若自动上传全部失败，请改用方式 A。

## 预期执行结果

### 控制台输出示例

```
============================================================
  MinerU 云端 API — MVP 测试 Pipeline
  启动时间: 2026-05-24 15:30:00
============================================================

[配置] API 地址: https://mineru.net/api/v4/extract/task
[配置] 语言: ch, OCR: false, 公式: true, 表格: true
[文件] 使用本地文件: d:\...\mineru-mvp-test\sample.pdf
[上传] 正在上传到 file.io ...
[上传] 成功: https://file.io/abc123

[提交] 正在提交解析任务...
   URL: https://file.io/abc123
   参数: {"language": "ch", "is_ocr": false, ...}
   task_id: a90e6ab6-44f3-4554-b459-b62fe4c6b436

[轮询] 等待任务完成 (最多 300s)...
   [running] ==========> 18s | Pages: 1/2
   [done] ==================> 25s | Pages: 2/2

[下载] 正在下载结果 ZIP ...
   [====================] 100%

[解压] 完成 → d:\...\mineru-mvp-test\output\a90e6ab6

============================================================
  解析结果摘要
============================================================

  输出目录: d:\...\mineru-mvp-test\output\a90e6ab6
  文件数量: 4

  文件清单:
    a90e6ab6_content_list.json                2.3 KB  ← 内容列表
    a90e6ab6_layout.json                      8.1 KB  ← 布局中间结果
    a90e6ab6_model.json                       15.2 KB ← 模型原始输出
    full.md                                   3.5 KB  ← Markdown 输出

  统计:
    Markdown 文件: 1
    JSON 文件:     3

  Content List 元素统计:
    [T] text            12  个
    [B] table           2   个
    [E] equation        3   个

============================================================

[完成] 总耗时: 28.3s
[完成] 输出目录: d:\...\mineru-mvp-test\output\a90e6ab6
```

### 输出文件说明

| 文件 | 说明 |
|---|---|
| `full.md` | 完整的 Markdown 格式文档 |
| `*_content_list.json` | 按阅读顺序排列的结构化内容列表（text/table/equation/image） |
| `*_layout.json` | 按页组织的块级布局信息（含 bbox 坐标） |
| `*_model.json` | 模型推理原始输出 |

## 常见问题

**Q: 上传文件时提示所有服务失败？**

手动将 PDF 上传至云存储，在 `.env` 中设置 `FILE_URL`。

**Q: 任务提交失败，返回 401？**

检查 `.env` 中 `MINERU_API_TOKEN` 是否有效。Token 过期需重新申请。

**Q: 轮询超时？**

增大 `.env` 中 `MAX_WAIT_SECONDS` 的值，或检查文件大小是否超限（≤200MB）。

**Q: 如何只解析指定页码范围？**

在 `run_mvp.py` 的 `parse_config` 字典中添加：
```python
"page_ranges": "1-10",
```

## 依赖

- Python >= 3.10
- requests
- python-dotenv
- fpdf2（仅用于生成示例 PDF）
