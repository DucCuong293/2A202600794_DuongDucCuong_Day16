from __future__ import annotations
import json
import os
import time
from typing import Any

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import JudgeResult, QAExample, ReflectionEntry


def _format_context(example: QAExample) -> str:
    return "\n".join(f"[{c.title}] {c.text}" for c in example.context)


def _extract_final_answer(text: str) -> str:
    """Pull the answer out of the Actor's 'FINAL ANSWER: ...' format, with a
    graceful fallback to the last non-empty line."""
    for line in reversed(text.strip().splitlines()):
        stripped = line.strip()
        if stripped.upper().startswith("FINAL ANSWER:"):
            return stripped.split(":", 1)[1].strip()
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return lines[-1] if lines else text.strip()


def _loads_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):text.rfind("}") + 1]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


class LLMRuntime:
    """Real LLM runtime backed by the OpenAI Chat Completions API.

    Captures the genuine token usage (`response.usage.total_tokens`) and
    wall-clock latency of every call, replacing the hardcoded estimates.
    """

    name = "llm"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        from openai import OpenAI  # imported lazily so mock runs need no openai install

        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def _chat(self, system: str, user: str, json_mode: bool = False) -> tuple[str, int, int]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        resp = self.client.chat.completions.create(**kwargs)
        latency_ms = int((time.perf_counter() - start) * 1000)
        content = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return content, tokens, latency_ms

    def actor(self, example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> tuple[str, int, int]:
        parts = [f"QUESTION:\n{example.question}", f"\nCONTEXT:\n{_format_context(example)}"]
        if reflection_memory:
            notes = "\n".join(f"- {m}" for m in reflection_memory)
            parts.append(f"\nREFLECTION NOTES from previous attempts (apply these):\n{notes}")
        content, tokens, latency = self._chat(ACTOR_SYSTEM, "\n".join(parts))
        return _extract_final_answer(content), tokens, latency

    def judge(self, example: QAExample, answer: str) -> tuple[JudgeResult, int, int]:
        user = (
            f"QUESTION:\n{example.question}\n\n"
            f"GOLD ANSWER:\n{example.gold_answer}\n\n"
            f"PREDICTED ANSWER:\n{answer}"
        )
        content, tokens, latency = self._chat(EVALUATOR_SYSTEM, user, json_mode=True)
        data = _loads_json(content)
        result = JudgeResult(
            score=int(data.get("score", 0)),
            reason=str(data.get("reason", "")),
            missing_evidence=list(data.get("missing_evidence", []) or []),
            spurious_claims=list(data.get("spurious_claims", []) or []),
        )
        return result, tokens, latency

    def reflect(self, example: QAExample, attempt_id: int, judge: JudgeResult) -> tuple[ReflectionEntry, int, int]:
        user = (
            f"QUESTION:\n{example.question}\n\n"
            f"WRONG ANSWER:\n(see judge feedback below)\n\n"
            f"JUDGE FEEDBACK:\n"
            f"- reason: {judge.reason}\n"
            f"- missing_evidence: {judge.missing_evidence}\n"
            f"- spurious_claims: {judge.spurious_claims}\n\n"
            f"CONTEXT:\n{_format_context(example)}"
        )
        content, tokens, latency = self._chat(REFLECTOR_SYSTEM, user, json_mode=True)
        data = _loads_json(content)
        entry = ReflectionEntry(
            attempt_id=attempt_id,
            failure_reason=str(data.get("failure_reason", judge.reason)),
            lesson=str(data.get("lesson", "")),
            next_strategy=str(data.get("next_strategy", "")),
        )
        return entry, tokens, latency
