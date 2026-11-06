# Talking-avatar options audit (2026-10)

Hardware here: Apple M4 (arm64, Metal/MPS, no CUDA, no NVIDIA GPU). This audit is from project documentation knowledge; **none of these were installed or run in this repo** except where stated.

| Option | Needs | Fits this Mac? | Verdict |
|---|---|---|---|
| MuseTalk (TMElyralab) | CUDA GPU (PyTorch + mmpose stack) | No | Not runnable locally. Adapter slot kept (`MUSETALK_DIR`); intended for a rented/own CUDA box. |
| SadTalker | CUDA recommended; CPU possible but very slow | Not practical | Not integrated. |
| Wav2Lip | CPU/MPS possible, old low-res (96px face) | Technically | Quality below professional use; not integrated. |
| Hallo / EchoMimic / newer diffusion talkers | 12-24 GB CUDA VRAM | No | Cloud GPU only. |
| HeyGen API | API key + avatar id, paid | Yes (external) | **Implemented** in `providers/avatar.py` from public API docs. Not verified against a live account. |
| Static portrait | none | Yes | Works, but is a still image: **not** a talking avatar. |

Recommendation: use `AVATAR_PROVIDER=heygen` (or a cloud-GPU MuseTalk endpoint) for talking instructor scenes; keep `static` for development. The pipeline records which provider produced each scene in `avatar_generations` and in the asset manifest (`talking_avatar: true|false`).
