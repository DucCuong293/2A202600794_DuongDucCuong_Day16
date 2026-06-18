# Lab 16 — Reflexion Agent

**Sinh viên:** Dương Đức Cường · **MSSV:** 2A202600794 · **Day 16**

Bài nộp triển khai và đánh giá **Reflexion Agent** — agent hỏi–đáp multi-hop có khả
năng **tự phản chiếu (self-reflection)** để sửa câu trả lời qua nhiều lượt thử, so
sánh với baseline **ReAct** một lượt. Toàn bộ scaffold đã được hoàn thiện và chạy
bằng **LLM thật (OpenAI gpt-4o-mini)**.

## Kết quả

| Báo cáo | Dữ liệu | ReAct EM | Reflexion EM | Autograde |
|---|---|---:|---:|---|
| `outputs/benchmark_run_llm/` | Benchmark tự sinh (148 records) | 1.00 | 1.00 | **100/100 + 20/20** |
| `outputs/golden_run_llm/` | Test set giảng viên (held-out, 40 records) | 0.90 | **1.00** | EM dùng để xếp hạng |

Trên test set giảng viên, Reflexion **xoá sạch 2 lỗi `incomplete_multi_hop`** mà ReAct
mắc. Ví dụ: *"Official languages of the country where the Atomium is located?"* —
ReAct trả `Dutch` (✗), Reflexion phản chiếu rồi hoàn thiện `Dutch, French, German` (✓).

Token và latency trong báo cáo là **số thật** lấy từ `usage.total_tokens` và
`time.perf_counter` của mỗi lời gọi API. Phân tích chi tiết: xem [REPORT.md](REPORT.md).

## Kiến trúc

Ba vai trò, mỗi vai trò một system prompt riêng ([prompts.py](src/reflexion_lab/prompts.py)):

| Vai trò | Nhiệm vụ | Output |
|---|---|---|
| **Actor** | Suy luận từng hop từ context (+ reflection notes) | `FINAL ANSWER: …` |
| **Evaluator** | Chấm 0/1 so với gold, nêu bằng chứng thiếu/sai | `JudgeResult` (JSON) |
| **Reflector** | Phân tích lỗi → chiến thuật mới | `ReflectionEntry` (JSON) |

Vòng lặp: Actor → Evaluator; nếu sai và còn lượt → Reflector ghi `next_strategy` vào
`reflection_memory` để Actor dùng cho lượt sau.

## Cách chạy

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # rồi điền OPENAI_API_KEY

python tools/make_dataset.py                          # sinh data/benchmark_set.json

# Mock (miễn phí, deterministic) — kiểm tra flow
python run_benchmark.py --dataset data/benchmark_set.json --out-dir outputs/run --mode mock

# LLM thật — báo cáo rubric
python run_benchmark.py --dataset data/benchmark_set.json --out-dir outputs/benchmark_run_llm --mode llm
python autograde.py --report-path outputs/benchmark_run_llm/report.json

# LLM thật — test set giảng viên (held-out)
python run_benchmark.py --dataset data/hotpot_golden.json --out-dir outputs/golden_run_llm --mode llm
```

## Cấu trúc mã nguồn

| File | Mô tả |
|---|---|
| `src/reflexion_lab/schemas.py` | Kiểu dữ liệu: `QAExample`, `RunRecord`, `JudgeResult`, `ReflectionEntry` |
| `src/reflexion_lab/prompts.py` | System prompt Actor / Evaluator / Reflector |
| `src/reflexion_lab/agents.py` | Vòng lặp ReAct + Reflexion, token/latency thật, phát hiện looping |
| `src/reflexion_lab/llm_runtime.py` | Runtime gọi OpenAI thật, bắt token + latency |
| `src/reflexion_lab/mock_runtime.py` | Runtime mock deterministic (autograde miễn phí) |
| `src/reflexion_lab/reporting.py` | Tổng hợp metric + phân tích failure mode + discussion |
| `src/reflexion_lab/utils.py` | `load_dataset`, `normalize_answer`, `save_jsonl` |
| `run_benchmark.py` / `autograde.py` | Chạy benchmark / chấm điểm |
| `tools/make_dataset.py` | Sinh bộ benchmark multi-hop (74 mẫu) |
| `REPORT.md` | Báo cáo phương pháp + phân tích kết quả |

## Bonus extensions đã triển khai

`structured_evaluator` · `reflection_memory` · `adaptive_max_attempts` ·
`benchmark_report_json` · `mock_mode_for_autograding`
