"""Real-model duration check: generate a storyboard section by section with the configured Ollama model and report
actual word counts vs budgets. Usage: python -m app.cli.real_llm_check [minutes]   (needs `ollama serve` and the model pulled)."""
import json
import sys
import time

from app.core.config import ROOT, get_settings
from app.models import Lesson
from app.providers.llm import OllamaProvider
from app.services import generation, lengthplan


def main(minutes: int = 3) -> int:
    s = get_settings()
    bundle = json.loads((ROOT / "lessons" / "sqli_fundamentals" / "bundle.json").read_text())
    lesson = Lesson(title=bundle["lesson_title"], summary=bundle["summary"], estimated_minutes=minutes)
    llm = OllamaProvider(s.ollama_url, s.ollama_model)
    t0, stats = time.time(), []
    orig = generation._ask

    def spy(llm_, task, prompt, model, retries=1):
        out = orig(llm_, task, prompt, model, retries)
        if task == "storyboard_section":
            sec = prompt.split("SECTION: ")[1].split("\n")[0]
            stats.append((sec, int(prompt.split("WORD_BUDGET: ")[1].split("\n")[0]), sum(len(x.narration.split()) for x in out.scenes), "previous" in prompt))
        return out
    generation._ask = spy
    try:
        sb = generation.build_storyboard_by_sections(lesson, bundle["script"], llm)
        verdict = "ACCEPTED"
    except Exception as e:  # noqa: BLE001
        sb, verdict = None, f"REJECTED: {e}"
    for sec, bud, words, corr in stats:
        print(f"{sec:18s} budget {bud:4d} words {words:4d} {'(correction round)' if corr else ''}")
    print(f"model={s.ollama_model} requested={minutes} min target={lengthplan.target_words(minutes)} words, elapsed {time.time() - t0:.0f}s -> {verdict}")
    if sb:
        print(f"actual {lengthplan.word_count(sb)} words, estimated {lengthplan.estimate_seconds(sb) / 60:.1f} min, preflight: {lengthplan.preflight(sb, minutes, 'ollama') or 'ok'}")
        (ROOT / "storage" / "manifests" / "real_llm_check.json").write_text(sb.model_dump_json(indent=1))
    return 0 if sb else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
