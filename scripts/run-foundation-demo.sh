#!/usr/bin/env bash

set -euo pipefail

repo_root=$(
  CDPATH=
  cd -- "$(dirname -- "$0")/.."
  pwd
)
port=${BENCHWARMER_DEMO_PORT:-8000}
server_pid=
data_root=

case "$port" in
'' | *[!0-9]*)
  printf 'BENCHWARMER_DEMO_PORT must be an integer from 1 through 65535.\n' >&2
  exit 2
  ;;
esac
if ((port < 1 || port > 65535)); then
  printf 'BENCHWARMER_DEMO_PORT must be an integer from 1 through 65535.\n' >&2
  exit 2
fi

if [[ -n ${BENCHWARMER_DATA_ROOT:-} ]]; then
  printf '%s\n' \
    'Unset BENCHWARMER_DATA_ROOT before running the demo.' \
    'The demo always creates isolated disposable state and never reuses private data.' >&2
  exit 2
fi

cleanup() {
  local status=$?
  trap - EXIT HUP INT TERM

  if [[ -n $server_pid ]]; then
    kill -TERM -- "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  if [[ -n $data_root && -d $data_root ]]; then
    rm -rf -- "$data_root"
  fi

  exit "$status"
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

cd -- "$repo_root"

printf 'Building the Svelte application...\n'
npm --prefix web run build

test -f web/build/200.html || {
  printf 'The frontend build did not produce web/build/200.html.\n' >&2
  exit 1
}

data_root=$(mktemp -d "${TMPDIR:-/tmp}/benchwarmer-foundation-demo.XXXXXX")
chmod 700 "$data_root"
export BENCHWARMER_DATA_ROOT=$data_root
export BENCHWARMER_UI_ROOT=$repo_root/web/build

printf 'Preparing sanitized fixture data...\n'
uv run alembic upgrade head
uv run python -m benchwarmer.services.fixtures \
  --load tests/fixtures/sources.json

printf '\nBenchwarmer foundation demo\n'
printf '  URL: http://127.0.0.1:%s\n' "$port"
printf '  Data: disposable state at %s\n' "$data_root"
printf '  Cleanup: stop with Ctrl-C; the disposable data directory is then removed.\n\n'

uv run uvicorn benchwarmer.api.app:create_app \
  --factory \
  --host 127.0.0.1 \
  --port "$port" &
server_pid=$!
wait "$server_pid"
server_pid=
