"""
Card Builder — §6.2 of enterprise-evolution-blueprint.

Multi-platform message card templates (Feishu/Mermaid/DingTalk/WeCom).
Uses a shared intermediate format and renders to platform-specific JSON.
"""

from __future__ import annotations


class CardBuilder:
    """Build platform-specific interactive message cards."""

    @staticmethod
    def feishu_qa_card(question: str, answer: str, sources: list[str],
                       query_id: str = "", detail_url: str = "") -> dict:
        """Feishu interactive card with feedback buttons."""
        source_lines = []
        for s in sources[:5]:
            source_lines.append(f"📄 {s[:80]}")
        if len(sources) > 5:
            source_lines.append(f"... 共 {len(sources)} 条来源")
        source_md = "\n".join(source_lines) if source_lines else "无明确来源"

        elements = [
            {
                "tag": "markdown",
                "content": f"{answer}\n\n---\n**来源**\n{source_md}",
            },
        ]

        # Feedback buttons
        if query_id:
            elements.append({
                "tag": "action",
                "layout": "flow",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "👍 有用"},
                        "type": "primary",
                        "value": f"positive|{query_id}",
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "👎 无用"},
                        "type": "danger",
                        "value": f"negative|{query_id}",
                    },
                ],
            })

        # Detail link
        if detail_url:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "📎 在网页中查看"},
                    "type": "default",
                    "url": detail_url,
                }],
            })

        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": "由 GraphRAG 知识引擎驱动"}],
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text",
                         "content": f"📊 {question[:40]}{'...' if len(question) > 40 else ''}"},
                "template": "blue",
            },
            "elements": elements,
        }

    @staticmethod
    def feishu_error_card(message: str = "抱歉，查询失败") -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "⚠ 错误"}, "template": "red"},
            "elements": [
                {"tag": "markdown", "content": message},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "GraphRAG Bot"}]},
            ],
        }

    @staticmethod
    def feishu_welcome_card() -> dict:
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": "🤖 GraphRAG 助手"}, "template": "green"},
            "elements": [
                {"tag": "markdown", "content": "你好！我是 GraphRAG 知识引擎助手。\n\n**我可以帮你：**\n• 查询 HSE 文档中的安全规范\n• 查找项目预算、进度等数据\n• 问答设备操作规程\n\n直接 @我 提问即可！"},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": "由 GraphRAG 知识引擎驱动"}]},
            ],
        }

    @staticmethod
    def dingtalk_markdown(answer: str, sources: list[str]) -> dict:
        """DingTalk markdown message (for future use)."""
        source_text = "\n".join([f"> {s[:60]}" for s in sources[:3]])
        text = f"## 查询结果\n\n{answer}\n\n---\n**来源**\n{source_text}"
        return {"msgtype": "markdown", "markdown": {"title": "GraphRAG 查询", "text": text}}

    @staticmethod
    def wecom_markdown(answer: str, sources: list[str]) -> dict:
        """WeCom markdown message (for future use)."""
        source_text = "\n".join([f"> {s[:60]}" for s in sources[:3]])
        text = f"## 查询结果\n{answer}\n\n**来源**\n{source_text}"
        return {"msgtype": "markdown", "markdown": {"content": text}}
