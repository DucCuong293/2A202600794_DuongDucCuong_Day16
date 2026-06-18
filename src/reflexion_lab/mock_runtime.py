from __future__ import annotations
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer

# Deterministic mock used to understand the flow and to autograde without API cost
# (`mock_mode_for_autograding` extension).
FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {"hp2": "incomplete_multi_hop", "hp4": "wrong_final_answer", "hp6": "entity_drift", "hp8": "entity_drift"}


def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> str:
    if example.qid not in FIRST_ATTEMPT_WRONG:
        return example.gold_answer
    if agent_type == "react":
        return FIRST_ATTEMPT_WRONG[example.qid]
    if attempt_id == 1 and not reflection_memory:
        return FIRST_ATTEMPT_WRONG[example.qid]
    return example.gold_answer


def evaluator(example: QAExample, answer: str) -> JudgeResult:
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return JudgeResult(score=1, reason="Final answer matches the gold answer after normalization.")
    if normalize_answer(answer) == "london":
        return JudgeResult(score=0, reason="The answer stopped at the birthplace city and never completed the second hop to the river.", missing_evidence=["Need to identify the river that flows through London."], spurious_claims=[])
    return JudgeResult(score=0, reason="The final answer selected the wrong second-hop entity.", missing_evidence=["Need to ground the answer in the second paragraph."], spurious_claims=[answer])


def reflector(example: QAExample, attempt_id: int, judge: JudgeResult) -> ReflectionEntry:
    strategy = "Do the second hop explicitly: birthplace city -> river through that city." if example.qid == "hp2" else "Verify the final entity against the second paragraph before answering."
    return ReflectionEntry(attempt_id=attempt_id, failure_reason=judge.reason, lesson="A partial first-hop answer is not enough; the final answer must complete all hops.", next_strategy=strategy)


class MockRuntime:
    """Runtime adapter exposing the actor/judge/reflect interface used by the
    agents, returning a deterministic (result, tokens, latency_ms) triple so the
    benchmark stays reproducible and free to run during autograding."""

    name = "mock"

    def actor(self, example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str]) -> tuple[str, int, int]:
        answer = actor_answer(example, attempt_id, agent_type, reflection_memory)
        tokens = 320 + attempt_id * 65 + (120 if agent_type == "reflexion" else 0)
        latency = 160 + attempt_id * 40 + (90 if agent_type == "reflexion" else 0)
        return answer, tokens, latency

    def judge(self, example: QAExample, answer: str) -> tuple[JudgeResult, int, int]:
        return evaluator(example, answer), 90, 70

    def reflect(self, example: QAExample, attempt_id: int, judge: JudgeResult) -> tuple[ReflectionEntry, int, int]:
        return reflector(example, attempt_id, judge), 110, 85
