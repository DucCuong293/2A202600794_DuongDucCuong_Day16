from __future__ import annotations
import json
from pathlib import Path
import typer
from dotenv import load_dotenv
from rich import print

load_dotenv()  # read OPENAI_API_KEY (and OPENAI_MODEL) from a local .env file
from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.mock_runtime import MockRuntime
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl
app = typer.Typer(add_completion=False)


def _make_runtime(mode: str, model: str | None):
    if mode == "mock":
        return MockRuntime()
    if mode == "llm":
        from src.reflexion_lab.llm_runtime import LLMRuntime
        return LLMRuntime(model=model)
    raise typer.BadParameter("mode must be 'mock' or 'llm'")


@app.command()
def main(
    dataset: str = "data/hotpot_mini.json",
    out_dir: str = "outputs/sample_run",
    reflexion_attempts: int = 3,
    mode: str = typer.Option("mock", help="'mock' (deterministic, free) or 'llm' (real OpenAI calls)."),
    model: str = typer.Option(None, help="LLM model id, e.g. gpt-4o-mini. Only used when --mode llm."),
) -> None:
    examples = load_dataset(dataset)
    runtime = _make_runtime(mode, model)
    react = ReActAgent(runtime=runtime)
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts, runtime=runtime)
    react_records = [react.run(example) for example in examples]
    reflexion_records = [reflexion.run(example) for example in examples]
    all_records = react_records + reflexion_records
    out_path = Path(out_dir)
    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)
    report = build_report(all_records, dataset_name=Path(dataset).name, mode=mode)
    json_path, md_path = save_report(report, out_path)
    print(f"[green]Saved[/green] {json_path}")
    print(f"[green]Saved[/green] {md_path}")
    print(json.dumps(report.summary, indent=2))


if __name__ == "__main__":
    app()
