#!/usr/bin/env bash
# Entry point do container.
#   run-all        (padrão) roda o pipeline inteiro e imprime o resumo
#   streamlit      sobe o dashboard interativo
set -euo pipefail

MODE="${1:-run-all}"

case "$MODE" in
  run-all)
    echo ">>> Pipeline completo (dados via API, ~200 MB)."
    python main.py
    ;;
  streamlit)
    echo ">>> Dashboard em http://localhost:8501"
    streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    echo "Uso: entrypoint.sh [run-all|streamlit|shell]"
    exit 1
    ;;
esac
