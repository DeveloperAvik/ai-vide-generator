## What and why

## How I tested
<!-- Commands run and results. Say honestly what you could NOT test (live LLM, YouTube, n8n, Docker, other OSes). -->

## Checklist
- [ ] `cd backend && python -m pytest -q` passes
- [ ] `npx tsc --noEmit` passes in `frontend/` and `video-engine/` (if touched)
- [ ] No secrets, `.env`, media, model files or database dumps are included
- [ ] New third-party code/assets are recorded in `THIRD_PARTY_NOTICES.md` / `MODEL_AND_ASSET_LICENSES.md`
- [ ] Safety invariants (human approval gates, no execution of LLM text, subprocess allow-list) are unchanged, or the change is explained
- [ ] Docs updated if behaviour or configuration changed
