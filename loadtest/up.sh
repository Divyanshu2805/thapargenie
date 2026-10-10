#!/usr/bin/env bash
# Bring the stack up, add the network delays and seed it. Run once before run.sh.
#   LT_EXPORT_DIR: a folder holding the crawler export (chunks.jsonl.gz). When set, it is
#     imported as the knowledge base with offline embeddings (no AI calls); pages already
#     imported are skipped. Without a knowledge base every answer is "not found".
#   LT_DB_MS (default 2): round trip Render Singapore -> Supabase Singapore, per statement
#   LT_FIREBASE_MS (default 150): one Firebase "is this session revoked" lookup
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1

docker compose build api emulator
docker compose up -d db emulator toxiproxy
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:8474/version >/dev/null 2>&1 && break
  sleep 1
done
toxic() {  # proxy, milliseconds
  curl -fsS -X DELETE "http://127.0.0.1:8474/proxies/$1/toxics/delay" >/dev/null 2>&1 || true
  curl -fsS -X POST "http://127.0.0.1:8474/proxies/$1/toxics" \
    -d "{\"name\":\"delay\",\"type\":\"latency\",\"stream\":\"downstream\",\"attributes\":{\"latency\":$2,\"jitter\":$(( $2 / 4 ))}}" >/dev/null
}
toxic db "${LT_DB_MS:-2}"
toxic firebase "${LT_FIREBASE_MS:-150}"
docker compose run --rm -T setup
if [ -n "${LT_EXPORT_DIR:-}" ]; then
  docker compose run --rm -T -v "$LT_EXPORT_DIR:/export:ro" setup \
    python manage.py import_crawler_export /export
fi
