#!/usr/bin/env bash
# compat_check.sh — core probado contra sus consumidores (D8, §6.1).
#
# Contrato (se implementa en la semana 13, con v1.0):
#   - corre las suites de 5 consumidores no deprecados:
#     3 recientes + 2 con pins antiguos (§6.1 de ARCHITECTURE.md);
#   - resuelve secrets y APIs vivas con record/replay, nunca API keys en CI;
#   - un merge a main no puede romper a esos 5 consumidores.
#
# Estado actual: stub con firma definida. Deuda documentada hacia sem. 13.

set -euo pipefail

usage() {
  echo "uso: compat_check.sh <main_branch> [consumidores...]" >&2
  exit 2
}

[[ $# -ge 1 ]] || usage

MAIN_BRANCH=$1
shift
CONSUMERS=("$@")

echo "compat_check: '${MAIN_BRANCH}' contra ${#CONSUMERS[@]} consumidores"
echo "compat_check: stub de sem. 1 — implementar en sem. 13 (v1.0)"
exit 1