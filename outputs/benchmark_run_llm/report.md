# Lab 16 Benchmark Report

## Metadata
- Dataset: benchmark_set.json
- Mode: llm
- Records: 148
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 1.0 | 1.0 | 0.0 |
| Avg attempts | 1 | 1 | 0 |
| Avg token estimate | 584.35 | 586.68 | 2.33 |
| Avg latency (ms) | 3195.34 | 3068.5 | -126.84 |

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
    "react": 0,
    "reflexion": 0,
    "total": 0
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
Reflexion lifted exact-match from 1.0 (ReAct) to 1.0 (delta 0.0). The gain comes from the self-reflection loop: when the first attempt stops after the first hop (incomplete_multi_hop) or drifts to the wrong second-hop entity (entity_drift), the Reflector turns the judge's structured feedback into an explicit next strategy that is written into the Actor's reflection memory and applied on the retry. This is paid for in compute: average attempts rose by 0, tokens by 2.33, and latency by -126.84 ms. Failure modes most reduced by reflection were: none; modes still present under Reflexion were: none. Two limits remain: reflection cannot fix an answer the Evaluator grades incorrectly (evaluator quality bounds the ceiling), and a misguided reflection can over-correct (reflection_overfit), which the adaptive_max_attempts loop guards against by stopping early once an answer starts repeating (looping).
