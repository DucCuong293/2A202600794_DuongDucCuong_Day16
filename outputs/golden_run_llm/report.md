# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_golden.json
- Mode: llm
- Records: 40
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.9 | 1.0 | 0.1 |
| Avg attempts | 1 | 1.05 | 0.05 |
| Avg token estimate | 622.8 | 672.3 | 49.5 |
| Avg latency (ms) | 3452.65 | 3369.55 | -83.1 |

## Failure modes
```json
{
  "entity_drift": {
    "description": "The agent completed the hops but latched onto the wrong final entity.",
    "react": 0,
    "reflexion": 0,
    "total": 0
  },
  "incomplete_multi_hop": {
    "description": "The agent answered the first hop but never completed the remaining hop(s).",
    "react": 2,
    "reflexion": 0,
    "total": 2
  },
  "looping": {
    "description": "The agent repeated the same wrong answer across attempts without progress.",
    "react": 0,
    "reflexion": 0,
    "total": 0
  },
  "reflection_overfit": {
    "description": "A reflection over-corrected and pushed the agent away from the right answer.",
    "react": 0,
    "reflexion": 0,
    "total": 0
  },
  "wrong_final_answer": {
    "description": "The final answer was wrong for a reason not captured by a more specific mode.",
    "react": 0,
    "reflexion": 0,
    "total": 0
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- adaptive_max_attempts
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
Reflexion lifted exact-match from 0.9 (ReAct) to 1.0 (delta 0.1). The gain comes from the self-reflection loop: when the first attempt stops after the first hop (incomplete_multi_hop) or drifts to the wrong second-hop entity (entity_drift), the Reflector turns the judge's structured feedback into an explicit next strategy that is written into the Actor's reflection memory and applied on the retry. This is paid for in compute: average attempts rose by 0.05, tokens by 49.5, and latency by -83.1 ms. Failure modes most reduced by reflection were: incomplete_multi_hop; modes still present under Reflexion were: none. Two limits remain: reflection cannot fix an answer the Evaluator grades incorrectly (evaluator quality bounds the ceiling), and a misguided reflection can over-correct (reflection_overfit), which the adaptive_max_attempts loop guards against by stopping early once an answer starts repeating (looping).
