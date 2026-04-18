#!/usr/bin/env bash
set -euo pipefail
# Download spaCy English model for NER.
# Run once after install: bash apps/api/scripts/download_models.sh
python -m spacy download en_core_web_sm
echo "spaCy en_core_web_sm downloaded successfully."
