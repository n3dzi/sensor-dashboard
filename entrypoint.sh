#!/bin/sh
set -e

mkdir -p /app/data

if [ ! -f "/app/data/analysis.db" ]; then
  echo "Datenbank nicht gefunden – wird generiert..."
  python analyse.py
fi

exec streamlit run app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true
