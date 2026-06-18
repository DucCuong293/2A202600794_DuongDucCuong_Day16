from __future__ import annotations
from typing import Literal, Optional, TypedDict
from pydantic import BaseModel, Field

class ContextChunk(BaseModel):
    title: str
    text: str

class QAExample(BaseModel):
    qid: str
    difficulty: Literal["easy", "medium", "hard"]
    question: str
    gold_answer: str
    context: list[ContextChunk]

class JudgeResult(BaseModel):
    """Structured verdict produced by the Evaluator/Judge.

    `structured_evaluator` extension: instead of a bare 0/1, the judge also
    returns a human-readable reason plus the evidence it found missing or
    spurious, so the Reflector has concrete material to reason over.
    """
    score: int = Field(ge=0, le=1, description="1 if the predicted answer matches the gold answer, else 0.")
    reason: str = Field(description="Short justification for the score.")
    missing_evidence: list[str] = Field(default_factory=list, description="Facts the answer failed to ground.")
    spurious_claims: list[str] = Field(default_factory=list, description="Unsupported / wrong claims in the answer.")

class ReflectionEntry(BaseModel):
    """One self-reflection produced after a failed attempt."""
    attempt_id: int = Field(description="The attempt that this reflection analyses.")
    failure_reason: str = Field(description="Why the previous answer was wrong.")
    lesson: str = Field(description="Generalised lesson learned from the failure.")
    next_strategy: str = Field(description="Concrete strategy the Actor should try next.")

class AttemptTrace(BaseModel):
    attempt_id: int
    answer: str
    score: int
    reason: str
    reflection: Optional[ReflectionEntry] = None
    token_estimate: int = 0
    latency_ms: int = 0

class RunRecord(BaseModel):
    qid: str
    question: str
    gold_answer: str
    agent_type: Literal["react", "reflexion"]
    predicted_answer: str
    is_correct: bool
    attempts: int
    token_estimate: int
    latency_ms: int
    failure_mode: Literal["none", "entity_drift", "incomplete_multi_hop", "wrong_final_answer", "looping", "reflection_overfit"]
    reflections: list[ReflectionEntry] = Field(default_factory=list)
    traces: list[AttemptTrace] = Field(default_factory=list)

class ReportPayload(BaseModel):
    meta: dict
    summary: dict
    failure_modes: dict
    examples: list[dict]
    extensions: list[str]
    discussion: str

class ReflexionState(TypedDict):
    question: str
    context: list[str]
    trajectory: list[str]
    reflection_memory: list[str]
    attempt_count: int
    success: bool
    final_answer: str
