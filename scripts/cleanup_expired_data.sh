#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$PROJECT_DIR/.venv/bin/flask" ]]; then
  FLASK_BIN="$PROJECT_DIR/.venv/bin/flask"
elif [[ -x "$PROJECT_DIR/venv/bin/flask" ]]; then
  FLASK_BIN="$PROJECT_DIR/venv/bin/flask"
elif command -v flask >/dev/null 2>&1; then
  FLASK_BIN="$(command -v flask)"
else
  echo "flask 실행 파일을 찾을 수 없습니다." >&2
  exit 1
fi

cd "$PROJECT_DIR"
exec "$FLASK_BIN" --app app cleanup-expired-data