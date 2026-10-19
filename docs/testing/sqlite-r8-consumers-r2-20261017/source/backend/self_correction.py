"""
Self-Correction Module -- §3.3 of rag-engineering-blueprint-v1.0.
Validates LLM answers and triggers regeneration when issues found.
Max 2 correction rounds. Checks citations, numbers, and contradictions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class CorrectedResult:
    answer_text: str
    correction_rounds: int
    corrections_made: list[str] = field(default_factory=list)
    final_passed: bool = False

class SelfCorrection:
    """Validates generated answers and triggers correction on failure.

    Three validation steps run in sequence:
      1. Verify all [c#####] and [n####] citations exist in context.
      2. Verify significant numbers in the answer appear in context.
      3. Check for contradiction indicators (但是/然而/不过 + negation).

    Usage:
        corrector = SelfCorrection(max_rounds=2)
        result = corrector.correct(
            answer_text=answer,
            context_chunks=chunks,
            query=user_query,
            generator_func=my_gen,
        )
    """

    def __init__(self, max_rounds: int = 2):
        if max_rounds < 0:
            raise ValueError("max_rounds must be >= 0")
        self.max_rounds = max_rounds

    def correct(
        self,
        answer_text: str,
        context_chunks: list[dict],
        query: str,
        generator_func: Callable[..., str],
    ) -> CorrectedResult:
        """Validate and correct an LLM answer across up to max_rounds attempts.

        Args:
            answer_text: Initial answer from the LLM generator.
            context_chunks: Source chunks with 'chunk_id' and 'text'.
            query: Original user question.
            generator_func: Callable accepting error_hints keyword argument
                and returning a corrected answer string.
        """
        corrections_made: list[str] = []
        current_answer = answer_text

        # Validate the initial answer and every generated correction, including
        # the final allowed one. Validation itself consumes no generation budget.
        for round_idx in range(self.max_rounds + 1):
            error_hints: list[str] = []
            passed, errs = self._verify_citations(current_answer, context_chunks)
            if not passed:
                error_hints.extend(errs)
            passed, errs = self._verify_numbers(current_answer, context_chunks)
            if not passed:
                error_hints.extend(errs)
            passed, errs = self._check_contradictions(current_answer)
            if not passed:
                error_hints.extend(errs)

            if not error_hints:
                return CorrectedResult(
                    answer_text=current_answer,
                    correction_rounds=round_idx,
                    corrections_made=corrections_made,
                    final_passed=True,
                )

            if round_idx == self.max_rounds:
                break

            corrections_made.extend(error_hints)
            try:
                current_answer = generator_func(error_hints=error_hints)
            except Exception as exc:  # noqa: BLE001  # 单轮修正生成失败仅记录该轮错误提示，不中断整个自纠正循环
                corrections_made.append(
                    f"修正生成调用失败（第{round_idx + 1}轮）: {exc}"
                )
                break

        warning = (
            f"\n\n[自修正警告: 经过 {self.max_rounds} 轮修正后仍存在"
            f"未解决的问题，以下答案仅供参考]"
        )
        return CorrectedResult(
            answer_text=current_answer + warning,
            correction_rounds=self.max_rounds,
            corrections_made=corrections_made,
            final_passed=False,
        )
    # -- Validation Step 1: Citation Check --

    def _verify_citations(
        self, answer: str, context_chunks: list[dict]
    ) -> tuple[bool, list[str]]:
        """Check all [c#####] and [n####] citations exist in context chunks."""
        cited_ids: list[str] = []
        cited_ids.extend(re.findall(r'\[(c\d{5})\]', answer))
        cited_ids.extend(re.findall(r'\[(n\d{4})\]', answer))

        if not cited_ids:
            return True, []

        valid_ids: set[str] = set()
        for chunk in context_chunks:
            cid = chunk.get("chunk_id", "")
            if cid:
                valid_ids.add(cid)
            text = chunk.get("text", "")
            for nid in re.findall(r'"node_id":\s*"([^"]+)"', text):
                valid_ids.add(nid)

        error_hints: list[str] = []
        for cid in sorted(set(cited_ids)):
            if cid in valid_ids:
                continue
            if any(cid in vid or vid in cid for vid in valid_ids):
                continue
            error_hints.append(
                f"引用 [{cid}] 在上下文资料中不存在，"
                f"可能为幻觉引用，请移除或替换为有效来源"
            )
        return len(error_hints) == 0, error_hints
    # -- Validation Step 2: Number Check --

    def _verify_numbers(
        self, answer: str, context_chunks: list[dict]
    ) -> tuple[bool, list[str]]:
        """Extract significant numbers from answer and verify they appear in context."""
        numbers = re.findall(r'\b(\d+\.?\d*%?)\b', answer)
        if not numbers:
            return True, []

        context_corpus = " ".join(
            chunk.get("text", "") for chunk in context_chunks
        )

        error_hints: list[str] = []
        seen: set[str] = set()

        for num in numbers:
            if num in seen:
                continue
            seen.add(num)

            clean = num.replace("%", "")
            try:
                val = float(clean)
                if val < 10 and "." not in clean and "%" not in num:
                    continue
            except ValueError:
                continue

            if num in context_corpus or clean in context_corpus:
                continue

            error_hints.append(
                f'数值 "{num}" 在上下文资料中未找到对应来源，'
                f"请核实该数值准确性或补充引用"
            )

        return len(error_hints) == 0, error_hints

    # -- Validation Step 3: Contradiction Check --

    def _check_contradictions(self, answer: str) -> tuple[bool, list[str]]:
        """Detect contradiction indicators like 但是/然而/不过 + negation."""
        connectors = ["但是", "然而", "不过"]
        negation_kw = ["不", "未", "无", "没有", "无法", "否"]

        error_hints: list[str] = []
        for sent in re.split(r'[。；！？\n]', answer):
            if len(sent.strip()) < 10:
                continue
            for conn in connectors:
                if conn not in sent:
                    continue
                idx = sent.find(conn)
                after = sent[idx + len(conn):]
                if any(kw in after[:20] for kw in negation_kw):
                    error_hints.append(
                        f'检测到转折表述含"{conn}"且后文出现否定词，'
                        f'可能存在逻辑矛盾: "{sent.strip()[:60]}..."'
                    )
                    break
            if error_hints:
                break

        return len(error_hints) == 0, error_hints
