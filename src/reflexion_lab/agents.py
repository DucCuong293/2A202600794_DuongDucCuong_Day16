from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

from .mock_runtime import FAILURE_MODE_BY_QID, MockRuntime
from .schemas import AttemptTrace, JudgeResult, QAExample, ReflectionEntry, RunRecord
from .utils import normalize_answer


def _classify_failure(example: QAExample, judge: JudgeResult, looping: bool) -> str:
    """Best-effort failure-mode classification from the judge's structured output.
    Used when no hardcoded mock label exists (i.e. on real datasets / LLM runs)."""
    if example.qid in FAILURE_MODE_BY_QID:
        return FAILURE_MODE_BY_QID[example.qid]
    if looping:
        return "looping"
    if judge.spurious_claims:
        return "entity_drift"
    if judge.missing_evidence:
        return "incomplete_multi_hop"
    return "wrong_final_answer"


@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    runtime: Any = field(default_factory=MockRuntime)

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        seen_answers: set[str] = set()
        final_answer = ""
        final_score = 0
        looping = False
        last_judge = JudgeResult(score=0, reason="")

        for attempt_id in range(1, self.max_attempts + 1):
            answer, a_tok, a_lat = self.runtime.actor(example, attempt_id, self.agent_type, reflection_memory)
            judge, j_tok, j_lat = self.runtime.judge(example, answer)

            final_answer = answer
            final_score = judge.score
            last_judge = judge
            tokens = a_tok + j_tok
            latency = a_lat + j_lat
            reflection_entry: ReflectionEntry | None = None

            # adaptive_max_attempts: detect a repeated wrong answer (a loop) so we
            # can stop early instead of burning the remaining attempts.
            norm = normalize_answer(answer)
            if judge.score == 0 and norm in seen_answers:
                looping = True
            seen_answers.add(norm)

            # --- Reflexion loop -------------------------------------------------
            # If this is a Reflexion agent, the attempt failed, and attempts
            # remain, reflect on the failure and feed the new strategy back into
            # the Actor's memory for the next attempt.
            if judge.score != 1 and self.agent_type == "reflexion" and attempt_id < self.max_attempts and not looping:
                reflection_entry, r_tok, r_lat = self.runtime.reflect(example, attempt_id, judge)
                reflections.append(reflection_entry)
                reflection_memory.append(
                    f"Attempt {attempt_id} failed because: {reflection_entry.failure_reason} "
                    f"Lesson: {reflection_entry.lesson} Next strategy: {reflection_entry.next_strategy}"
                )
                tokens += r_tok
                latency += r_lat

            traces.append(AttemptTrace(
                attempt_id=attempt_id, answer=answer, score=judge.score, reason=judge.reason,
                reflection=reflection_entry, token_estimate=tokens, latency_ms=latency,
            ))

            if judge.score == 1 or looping:
                break

        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = "none" if final_score == 1 else _classify_failure(example, last_judge, looping)
        return RunRecord(
            qid=example.qid, question=example.question, gold_answer=example.gold_answer,
            agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score),
            attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency,
            failure_mode=failure_mode, reflections=reflections, traces=traces,
        )


class ReActAgent(BaseAgent):
    def __init__(self, runtime: Any | None = None) -> None:
        super().__init__(agent_type="react", max_attempts=1, runtime=runtime or MockRuntime())


class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, runtime: Any | None = None) -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts, runtime=runtime or MockRuntime())
