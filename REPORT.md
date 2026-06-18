# Lab 16 — Reflexion Agent · Báo cáo

> Báo cáo nộp kèm cho phần chấm tay (code quality, actual token logic, reasoning
> depth). Báo cáo benchmark dạng máy đọc nằm ở `outputs/combined_run_llm/report.json`.

## 1. Mục tiêu

Triển khai và đánh giá kiến trúc **Reflexion Agent** cho bài toán hỏi–đáp
multi-hop (kiểu HotpotQA), so sánh với baseline **ReAct** một lượt. Trọng tâm:
agent tự phản chiếu (self-reflection) sau mỗi lần trả lời sai để cải thiện ở lần
thử kế tiếp.

## 2. Kiến trúc

Ba vai trò, mỗi vai trò một system prompt riêng (`src/reflexion_lab/prompts.py`):

| Vai trò | Nhiệm vụ | Output |
|---|---|---|
| **Actor** | Đọc câu hỏi + context (+ reflection notes), suy luận từng hop | `FINAL ANSWER: <…>` |
| **Evaluator** (Judge) | Chấm 0/1 so với gold, nêu lý do + bằng chứng thiếu/sai | `JudgeResult` (JSON) |
| **Reflector** | Phân tích nguyên nhân sai → chiến thuật mới | `ReflectionEntry` (JSON) |

**Vòng lặp Reflexion** (`src/reflexion_lab/agents.py`): với mỗi attempt, Actor trả
lời → Evaluator chấm. Nếu đúng → dừng. Nếu sai và còn lượt → Reflector tạo
`ReflectionEntry`, ghi `next_strategy` vào `reflection_memory`; lượt sau Actor đọc
lại memory và áp dụng. ReAct là trường hợp đặc biệt `max_attempts = 1`.

```
Actor ──answer──▶ Evaluator ──score=1──▶ done
   ▲                  │ score=0
   │ reflection       ▼
reflection_memory ◀── Reflector  (chỉ với reflexion, khi còn attempt)
```

## 3. Phần đã triển khai (so với scaffold)

- **`schemas.py`** — `JudgeResult` (score, reason, missing_evidence, spurious_claims)
  và `ReflectionEntry` (attempt_id, failure_reason, lesson, next_strategy).
- **`prompts.py`** — 3 system prompt; Evaluator/Reflector ép trả JSON để parse
  ổn định.
- **`agents.py`** — vòng lặp Reflexion đầy đủ; **token & latency thật** cộng dồn từ
  runtime (không còn hardcode); phân loại failure-mode từ tín hiệu của Judge;
  phát hiện looping để dừng sớm.
- **`mock_runtime.py`** — bọc thành `MockRuntime` (deterministic, để autograde miễn phí).
- **`llm_runtime.py`** (mới) — `LLMRuntime` gọi **OpenAI** thật, parse output, bắt
  `usage.total_tokens` + đo `perf_counter` cho latency.
- **`run_benchmark.py`** — thêm `--mode mock|llm`, đọc `.env`.

### Actual token logic
Token/latency **không** còn là hằng số. Ở `llm_runtime.LLMRuntime._chat`:

```python
start = time.perf_counter()
resp = self.client.chat.completions.create(**kwargs)
latency_ms = int((time.perf_counter() - start) * 1000)
tokens = resp.usage.total_tokens if resp.usage else 0
```

Mỗi attempt cộng token của Actor + Evaluator (+ Reflector nếu có) và lưu vào
`AttemptTrace`; `RunRecord` tổng hợp toàn run.

## 4. Dữ liệu

- `data/benchmark_set.json` — **74 mẫu** multi-hop tự sinh bằng `tools/make_dataset.py`
  (mỗi câu khoá vào một landmark duy nhất nên chỉ có một chuỗi suy luận đúng; context
  chứa đủ mọi hop). Bao gồm cả 6 câu "đa đáp án" (ngôn ngữ chính thức nhiều thứ tiếng)
  để kiểm tra lỗi `incomplete_multi_hop`, cộng 8 câu seed.
- `data/hotpot_golden.json` — **20 mẫu** test set chính thức của giảng viên (held-out),
  **chỉ dùng để đánh giá**, không đưa vào benchmark tự sinh.

## 5. Thiết lập thực nghiệm

- Model: **OpenAI `gpt-4o-mini`**, `temperature = 0`.
- Reflexion `max_attempts = 3`; ReAct `max_attempts = 1`.
- **Báo cáo chấm rubric** (`outputs/benchmark_run_llm/`): chạy trên benchmark tự sinh,
  **148 records** (74 mỗi agent) — thoả mốc ≥100.
- **Báo cáo xếp hạng** (`outputs/golden_run_llm/`): chạy trên test set giảng viên
  (held-out), **40 records** (20 mỗi agent).

## 6. Kết quả (LLM thật)

**Benchmark tự sinh — `outputs/benchmark_run_llm/` (148 records):**

| Metric | ReAct | Reflexion |
|---|---:|---:|
| EM | 1.0000 | 1.0000 |
| Avg tokens (thật) | 584.4 | 586.7 |
| Avg latency ms (thật) | 3195 | 3069 |

Trên dữ liệu in-distribution (context chứa đủ đáp án), `gpt-4o-mini` đã đạt trần với
ReAct một lượt, nên không còn lỗi để Reflexion sửa — lợi ích của phản chiếu lộ rõ ở
dữ liệu khó / held-out bên dưới.

**Test set giảng viên (held-out) — `outputs/golden_run_llm/` (40 records):**

| Metric | ReAct | Reflexion | Δ |
|---|---:|---:|---:|
| EM | 0.90 | **1.00** | **+0.10** |
| Avg attempts | 1.00 | 1.05 | +0.05 |
| Avg tokens (thật) | 622.8 | 672.3 | +49.5 |

> Lưu ý: `autograde.py` trên báo cáo golden ra 90/100 chỉ vì 40 < 100 records — đây là
> tập xếp hạng (chấm theo EM), không phải báo cáo rubric. Điểm rubric đầy đủ
> (100/100 + 20/20) nằm ở `benchmark_run_llm`.

## 7. Phân tích failure mode (trên test set giảng viên)

| Failure mode | ReAct | Reflexion |
|---|---:|---:|
| incomplete_multi_hop | 2 | **0** |
| entity_drift / wrong_final_answer / looping / reflection_overfit | 0 | 0 |

Reflexion **xoá sạch** cả 2 lỗi của ReAct. Đây là loại lỗi đặc trưng của multi-hop:
agent trả lời đúng hop đầu nhưng dừng lại, không hoàn tất các hop còn lại.

## 8. Case study (Reflexion hoạt động trên dữ liệu unseen)

Câu `gold6` — *"What are the official languages of the country where the Atomium is located?"* (gold: *Dutch, French, and German*).

| Agent | Predicted | Đúng? | Attempts | Reflections |
|---|---|---|---:|---:|
| ReAct | `Dutch` | ✗ | 1 | 0 |
| Reflexion | `Dutch, French, German` | ✓ | 2 | 1 |

Diễn giải: ReAct chỉ lấy ngôn ngữ đầu tiên → Evaluator chấm 0 với
`missing_evidence` = các thứ tiếng còn thiếu → Reflector sinh `next_strategy` "liệt
kê **tất cả** ngôn ngữ chính thức từ đoạn context" → Actor lượt 2 hoàn tất → đúng.
Đây là minh chứng end-to-end cho giá trị của vòng phản chiếu trên dữ liệu chưa từng thấy.

## 9. Bonus extensions (đều triển khai thật)

| Extension | Mô tả |
|---|---|
| `structured_evaluator` | Judge trả JSON có lý do + bằng chứng thiếu/sai, không chỉ 0/1 |
| `reflection_memory` | Bộ nhớ chiến thuật được Actor đọc lại ở lượt sau |
| `adaptive_max_attempts` | Phát hiện lặp đáp án sai (looping) → dừng sớm, tiết kiệm token |
| `benchmark_report_json` | Xuất `report.json` máy đọc cho autograde |
| `mock_mode_for_autograding` | `MockRuntime` deterministic, chấm điểm không tốn API |

## 10. Trade-off & giới hạn

- **Chi phí:** Reflexion tốn thêm attempts/tokens; trên test set giảng viên là
  +0.05 attempt và +49.5 token/run vì chỉ một phần nhỏ câu cần thử lại.
- **Trần do Evaluator:** Reflexion không thể vượt chất lượng của Judge — nếu Judge
  chấm sai thì reflection vô nghĩa.
- **reflection_overfit:** một reflection lệch hướng có thể đẩy agent ra xa đáp án;
  `adaptive_max_attempts` giảm thiểu bằng cách dừng khi đáp án bắt đầu lặp.
- **Bão hoà in-distribution:** trên câu dễ (context chứa sẵn đáp án), ReAct đã gần
  100% nên lợi ích của Reflexion lộ rõ hơn ở câu khó / dữ liệu unseen (golden).

## 11. Tái lập

```bash
pip install -r requirements.txt
python tools/make_dataset.py                                  # tạo data/benchmark_set.json

# Mock (miễn phí, deterministic) — kiểm tra flow
python run_benchmark.py --dataset data/benchmark_set.json --out-dir outputs/benchmark_run --mode mock

# (1) Báo cáo rubric — benchmark tự sinh, LLM thật (cần OPENAI_API_KEY trong .env)
python run_benchmark.py --dataset data/benchmark_set.json --out-dir outputs/benchmark_run_llm --mode llm
python autograde.py --report-path outputs/benchmark_run_llm/report.json   # 100/100 + 20/20

# (2) Báo cáo xếp hạng — test set giảng viên (held-out), KHÔNG trộn vào benchmark
python run_benchmark.py --dataset data/hotpot_golden.json --out-dir outputs/golden_run_llm --mode llm
```

## 12. File nộp

| File | Mục đích |
|---|---|
| `outputs/benchmark_run_llm/report.json` · `.md` | Báo cáo rubric (100/100 + 20/20) |
| `outputs/golden_run_llm/report.json` · `.md` | Kết quả trên test set giảng viên (Reflexion EM 1.00) |
| `REPORT.md` | Bản tường thuật cho chấm tay |
