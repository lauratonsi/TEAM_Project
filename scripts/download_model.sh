#!/usr/bin/env bash
set -euo pipefail

URL=${1:-}
OUT_DIR="$(dirname "$0")/../models"
OUT_PATH=${2:-"$OUT_DIR/ggml-alpaca-7b-q4.bin"}

if [ -z "$URL" ]; then
  echo "Usage: $0 <model-download-url> [output-path]"
  exit 2
fi

mkdir -p "$OUT_DIR"
echo "Downloading model from $URL to $OUT_PATH"
curl -L --progress-bar "$URL" -o "$OUT_PATH"
echo "Download complete: $OUT_PATH"
