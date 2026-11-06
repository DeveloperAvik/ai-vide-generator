# Voices (all free, all local)

| Provider | Model / license | Notes |
|---|---|---|
| `kokoro` (default) | Kokoro-82M v1.0, Apache-2.0 (via `kokoro-onnx`; phonemizer uses espeak-ng, GPL-3, run locally) | Natural-sounding, CPU, ~4x realtime on the M4. 54 voices; English: `am_michael`, `am_adam`, `am_eric`, `am_liam`, `bm_george`, `bm_daniel`, `bm_lewis` (male); `af_heart`, `af_bella`, `af_nicole`, `bf_emma`, `bf_isabella` (female). Set `KOKORO_VOICE`, `KOKORO_SPEED` in `.env`. |
| `piper` | `en_US-lessac-medium` (see model card for license) | Fast, noticeably robotic. Kept as fallback. |
| `macos_say` | system voices | Development only; refused when `APP_ENV=production`. |

Install Kokoro: `pip install kokoro-onnx soundfile`, then download `kokoro-v1.0.onnx` (~326 MB) and `voices-v1.0.bin` (~28 MB) from
https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 into `voice/models/kokoro/`.

Technical terms are respelled for the voice only (`app/services/pronunciation.py`: XSS -> "X S S", nginx -> "engine-X" ...); captions keep the original text.
Speaking speed is measured per voice (`storage/manifests/voice_calibration__<voice>.json`) and drives the word budgets, so changing voice changes the plan automatically.
Listen before choosing: `storage/voice_samples/*.wav`.
