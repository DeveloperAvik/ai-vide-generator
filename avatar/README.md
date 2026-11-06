# Avatar providers

Instructor identity is one portrait: put your own image at `avatar/assets/instructor.png` (a labelled placeholder is generated if absent).
Use a licensed/own image or a clearly synthetic persona; YouTube requires disclosure of realistic synthetic media (uploads set `containsSyntheticMedia: true`).

| Provider | Status |
|---|---|
| `static` | Works now. Still portrait for the audio duration. **No lip-sync**; it is labelled as a fallback. |
| `musetalk` | Needs a CUDA GPU and your own MuseTalk install (`MUSETALK_DIR`). The wrapper `avatar/scripts/musetalk_run.sh` is yours to supply; until then the provider reports unavailable. |
| `heygen` | Paid. Enabled only with `HEYGEN_API_KEY`. Job submission is intentionally not wired to an unverified endpoint; it raises rather than faking a job. Implement `generate_avatar_video` against your account's avatar/voice ids. |
| SadTalker | Not implemented (same GPU requirement as MuseTalk); add a provider class following `AvatarProvider`. |
