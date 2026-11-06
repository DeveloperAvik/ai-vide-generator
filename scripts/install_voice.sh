#!/usr/bin/env bash
# Installs Piper TTS into the backend venv, downloads a voice, and writes PIPER_MODEL/VOICE_PROVIDER into .env.
set -euo pipefail
cat >&2 <<'MSG'
NOTICE: piper-tts is GPL-3.0-or-later and the en_US-lessac-medium voice is trained on data under a
research licence (Blizzard 2013 / Lessac). Commercial use is NOT established. For commercial work use
the Kokoro provider instead. See MODEL_AND_ASSET_LICENSES.md. Continuing in 5s (Ctrl+C to abort)...
MSG
sleep 5
cd "$(dirname "$0")/.."
VOICE=${1:-en_US-lessac-medium}
backend/.venv/bin/pip install -q piper-tts
mkdir -p voice/models
(cd voice/models && ../../backend/.venv/bin/python -m piper.download_voices "$VOICE")
sed -i.bak "s|^VOICE_PROVIDER=.*|VOICE_PROVIDER=piper|; s|^PIPER_MODEL=.*|PIPER_MODEL=$PWD/voice/models/$VOICE.onnx|" .env && rm -f .env.bak
echo "Piper ready: $VOICE"
