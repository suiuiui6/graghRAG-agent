#!/usr/bin/env python3
"""
生成示例 PDF 文件，用于 MinerU MVP 测试。

输出: sample.pdf — 包含中英文文本、表格、公式的混合文档。
依赖: pip install fpdf2
"""

import os
import sys
from fpdf import FPDF


def _find_chinese_fonts():
    """查找系统中支持中文的 Unicode 字体，返回 (regular_path, bold_path)。"""
    if sys.platform == "win32":
        fonts_dir = os.path.join(os.environ["WINDIR"], "Fonts")
        candidates = {
            "hei": os.path.join(fonts_dir, "simhei.ttf"),    # 黑体 → bold
            "kai": os.path.join(fonts_dir, "simkai.ttf"),    # 楷体 → regular
            "sun": os.path.join(fonts_dir, "simsun.ttc"),    # 宋体 → regular
            "fang": os.path.join(fonts_dir, "simfang.ttf"),  # 仿宋
        }
        # 优先: 楷体 regular + 黑体 bold
        reg = candidates.get("kai") if os.path.exists(candidates.get("kai", "")) else None
        if not reg and os.path.exists(candidates.get("sun", "")):
            reg = candidates["sun"]
        bold = candidates.get("hei") if os.path.exists(candidates.get("hei", "")) else None
        return reg, bold

    # macOS
    for d in ["/System/Library/Fonts", "/Library/Fonts"]:
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                path = os.path.join(d, f)
                if "PingFang" in f and f.endswith(".ttc"):
                    return path, path
                if "STHeiti" in f and f.endswith(".ttf"):
                    return path, path

    # Linux
    for d in ["/usr/share/fonts", "/usr/local/share/fonts"]:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith((".ttf", ".ttc")):
                        p = os.path.join(root, f)
                        if any(n in f.lower() for n in ["wqy", "noto", "wenquan", "droid", "cjk"]):
                            return p, p

    return None, None


class SamplePDF(FPDF):
    """生成含有多样内容的示例 PDF 文档（支持中英文混排）。"""

    def __init__(self, font_regular: str, font_bold: str | None = None):
        super().__init__()
        font_bold = font_bold or font_regular

        # 注册 Unicode 字体
        self.add_font("UNI", "", font_regular)
        self.add_font("UNI", "B", font_bold)

    def header(self):
        self.set_font("UNI", "B", 10)
        self.cell(0, 8, "MinerU MVP Test Document — Page Header", align="C")
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font("UNI", "", 8)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_title(self, text: str, level: int = 1):
        sizes = {1: 18, 2: 14, 3: 12}
        self.set_font("UNI", "B", sizes.get(level, 12))
        self.ln(4)
        self.cell(0, 10, text)
        self.ln(8)

    def add_body(self, text: str):
        self.set_font("UNI", "", 11)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_table(self, headers: list, rows: list, caption: str = ""):
        if caption:
            self.set_font("UNI", "", 10)
            self.cell(0, 6, caption)
            self.ln(8)

        col_w = (self.w - 20) / len(headers)
        self.set_font("UNI", "B", 10)
        for h in headers:
            self.cell(col_w, 8, h, border=1, align="C")
        self.ln()

        self.set_font("UNI", "", 10)
        for row in rows:
            for cell in row:
                self.cell(col_w, 7, str(cell), border=1, align="C")
            self.ln()
        self.ln(4)


def build_sample_pdf(output_path: str = "sample.pdf"):
    reg_path, bold_path = _find_chinese_fonts()
    if not reg_path:
        print("[回退] 未找到中文字体，使用纯英文 PDF 生成...")
        # 回退: 纯英文 Helvetica 版本
        return _build_english_only_pdf(output_path)

    print(f"[字体] Regular: {os.path.basename(reg_path)}")
    if bold_path:
        print(f"[字体] Bold:    {os.path.basename(bold_path)}")

    pdf = SamplePDF(reg_path, bold_path)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ============ 第一页 ============
    pdf.add_title("Chapter 1 系统架构总览", level=1)

    pdf.add_body(
        "This document describes the architecture of a multimodal Retrieval-Augmented "
        "Generation (RAG) system designed for intelligent question answering over "
        "heterogeneous document collections. The system integrates document parsing, "
        "knowledge graph extraction, vector indexing, and large language model inference "
        "into a unified pipeline."
    )

    pdf.add_title("1.1 系统设计目标", level=2)
    pdf.add_body(
        "本系统的核心设计目标包括：(1) 支持 PDF、DOCX 等多种格式文档的自动解析；"
        "(2) 基于知识图谱的结构化信息抽取与存储；(3) 结合向量检索与图检索的混合检索策略；"
        "(4) 利用大语言模型实现高质量的自然语言问答。系统整体采用微服务架构，"
        "各模块通过 RESTful API 进行通信。"
    )

    pdf.add_title("1.1.1 性能需求", level=3)
    pdf.add_body(
        "系统需支持每日 10,000 页以上的文档处理能力，单文档平均解析延迟不超过 30 秒。"
        "查询响应时间控制在 5 秒以内，知识图谱遍历支持 3 跳以内亚秒级响应。"
        "The system must process up to 10,000 pages per day with an average parsing "
        "latency under 30 seconds per document."
    )

    pdf.add_title("1.2 模型性能对比", level=2)
    pdf.add_table(
        headers=["模型名称", "准确率(%)", "召回率(%)", "F1值", "延迟(ms)"],
        rows=[
            ["BERT-base", "87.3", "82.5", "84.8", "45"],
            ["RoBERTa-large", "91.2", "88.7", "89.9", "120"],
            ["GPT-4o", "94.6", "92.1", "93.3", "850"],
            ["Gemini-2.5-Pro", "95.8", "93.4", "94.6", "720"],
            ["DeepSeek-v3", "93.1", "90.5", "91.8", "380"],
        ],
        caption="表 1：各语言模型在临床数据集上的实体抽取性能对比",
    )

    pdf.add_title("1.3 评测指标定义", level=2)
    pdf.add_body("以下为加权 F1 值及相关指标的计算公式：")
    pdf.add_body(
        "F1 = 2 * (Precision * Recall) / (Precision + Recall)               (1)\n"
        "Precision = TP / (TP + FP)                                          (2)\n"
        "Recall = TP / (TP + FN)                                             (3)"
    )

    # ============ 第二页 ============
    pdf.add_page()

    pdf.add_title("1.4 数据集统计信息", level=2)
    pdf.add_table(
        headers=["数据集", "文档数", "页数", "实体数", "平均实体/页"],
        rows=[
            ["临床病历", "5,200", "48,300", "1,245,000", "25.8"],
            ["法律合同", "3,100", "62,000", "890,000", "14.4"],
            ["学术论文", "12,800", "98,500", "3,420,000", "34.7"],
            ["财报文档", "1,500", "35,200", "520,000", "14.8"],
            ["技术手册", "800", "28,400", "310,000", "10.9"],
        ],
        caption="表 2：评测数据集统计摘要",
    )

    pdf.add_title("1.5 关键数值指标", level=2)
    pdf.add_body(
        "经过综合评测，系统在以下关键指标上达到预期效果：\n\n"
        "  * 文档解析准确率：96.8%\n"
        "  * 实体抽取 F1 值：91.2%\n"
        "  * 关系抽取 F1 值：87.5%\n"
        "  * 端到端问答准确率：89.3%\n"
        "  * 平均查询响应时间：2.8 秒\n"
        "  * 并发支持数：500 QPS\n"
        "  * 单日最大处理量：12,000 页"
    )

    pdf.add_title("1.6 结论与展望", level=2)
    pdf.add_body(
        "评测结果表明，所提出的混合 RAG 架构在文档理解任务上达到了业界领先水平。"
        "文档解析准确率 96.8%，实体抽取 F1 值 91.2%，关系抽取 F1 值 87.5%，"
        "系统能够从异构文档中稳健地提取结构化信息。"
        "The evaluation demonstrates that the proposed hybrid RAG architecture "
        "achieves state-of-the-art performance on document understanding tasks."
    )

    pdf.output(output_path)
    print(f"[生成] 示例 PDF 已保存: {output_path} ({pdf.page_no()} 页)")


def _build_english_only_pdf(output_path: str):
    """纯英文回退版本（无中文字体时使用）。"""
    pdf = FPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Chapter 1: System Architecture Overview")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        "This document describes the architecture of a multimodal Retrieval-Augmented "
        "Generation (RAG) system for intelligent question answering."
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "1.1 Performance Comparison")
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 10)
    headers = ["Model", "Accuracy (%)", "Recall (%)", "F1 Score", "Latency (ms)"]
    col_w = (pdf.w - 20) / len(headers)
    for h in headers:
        pdf.cell(col_w, 8, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 10)
    rows = [
        ["BERT-base", "87.3", "82.5", "84.8", "45"],
        ["GPT-4o", "94.6", "92.1", "93.3", "850"],
        ["Gemini-2.5-Pro", "95.8", "93.4", "94.6", "720"],
        ["DeepSeek-v3", "93.1", "90.5", "91.8", "380"],
    ]
    for row in rows:
        for cell in row:
            pdf.cell(col_w, 7, cell, border=1, align="C")
        pdf.ln()
    pdf.ln(6)

    pdf.output(output_path)
    print(f"[生成] 示例 PDF 已保存: {output_path} (纯英文, {pdf.page_no()} 页)")


if __name__ == "__main__":
    build_sample_pdf()
