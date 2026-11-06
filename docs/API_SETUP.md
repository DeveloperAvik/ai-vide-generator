# AI / provider setup

**Claude Pro is not an API key.** Pick one:
- **Mode A (free, manual):** keep `LLM_PROVIDER=mock`. Open `ai/prompts/lesson.md` in claude.ai, give it the topic + sources, paste the JSON into *Lessons → script editor → Save*. It is validated with the same schema as API output. The storyboard can be pasted through `PUT /api/lessons/{id}/storyboard` the same way.
- **Mode B (automated):** `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` from console.anthropic.com (pay-as-you-go, separate from Pro) — or `LLM_PROVIDER=ollama` with `ollama pull llama3.1` (free, local; JSON quality varies, validation will reject bad output).

`mock` produces generic template content for demos/tests and marks it as unverified. Do not publish mock output.

Add a provider: subclass `LLMProvider.complete` in `backend/app/providers/llm.py` and register it in `get_llm`.
Voice/avatar variables: see `.env.example`, `voice/README.md`, `avatar/README.md`.
