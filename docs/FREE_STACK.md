# Free, local-only stack

Nothing in the review / fact-checking / quality-gate pipeline needs a paid API, subscription or hosted service.

| Need | Used | Cost |
|---|---|---|
| Script writer, claim extraction, claim judge, technical reviewer | **Ollama** (local), e.g. `qwen2.5:7b-instruct` | free |
| Research sources | Public pages of OWASP, MITRE (CWE/CAPEC/ATT&CK), NIST/NVD, CISA, IETF/RFC Editor, kernel.org, man7, vendor docs, arXiv - fetched over HTTPS from an allow-list | free |
| Fact-check "search" | Deterministic passage retrieval over the stored text of those sources (no search API) | free |
| Voice | Kokoro (default) / Piper (fallback), local | free |
| Render | FFmpeg (Remotion optional), local | free |
| Storage / DB | local files + PostgreSQL | free |

Not used by this feature: Anthropic/OpenAI/Gemini APIs, ElevenLabs, HeyGen, paid search or fact-check APIs, paid hosting. (The older optional adapters for Anthropic/ElevenLabs/HeyGen still exist in the repo, unused; the review pipeline never calls them.)

## Configure Ollama for the reviewer
```
ollama serve                      # bound to localhost by default; do not expose it
ollama pull qwen2.5:7b-instruct   # once, manually. The studio never downloads models for you.
```
`.env` (or Settings in the dashboard for the provider):
```
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct   # writer
REVIEWER_MODEL=                    # empty = the same model reviews AFTER generation (sequential, one model in RAM)
                                   # set e.g. qwen2.5:14b-instruct for a stronger independent reviewer if RAM allows
REVIEWER_TIMEOUT_S=900
```
A different reviewer model is better than the same one (a model tends to approve its own mistakes), but on a 16 GB machine the 14B model is slow and tight; the pipeline works either way.

## Limits of "free"
* **Verification is retrieval-grounded, not truth-grounded.** A claim is `supported` only if the quoted evidence appears verbatim in a fetched official page and overlaps the claim. A small local model can still misjudge, and sources can be incomplete or wrong. Human review stays mandatory for anything marked `needs_human_review`, and every lesson still needs a human script approval and a human video approval.
* Only pages on the allow-list are fetched; PDFs (e.g. most arXiv papers, NIST PDFs) are stored as `unsupported_content`. Add HTML abstract/landing pages, or extend the allow-list in `services/research.py` (`OFFICIAL_HOSTS`).
* A 7B model finds fewer real errors than a human or a large hosted model. Treat "no findings" as "nothing the model noticed".
