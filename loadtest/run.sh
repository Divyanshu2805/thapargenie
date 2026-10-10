#!/usr/bin/env bash
# One load-test run: (re)start the API sized like a Render plan, run Locust, keep the CSVs.
#   ./run.sh NAME PLAN WORKERS THREADS SCENARIO USERS SECONDS
#   ./run.sh starter-2x8-ask16 starter 2 8 ask 16 90
# PLAN: free (0.1 CPU, 512 MB) | starter (0.5, 512 MB) | standard (1, 2 GB) | pro (2, 4 GB)
# Extra knobs come from the environment: LT_THROTTLE_ASK, LT_THROTTLE_USER, LT_POPULAR_SHARE.
set -euo pipefail
cd "$(dirname "$0")"
export MSYS_NO_PATHCONV=1
DB=${LT_DB:-thapargenie}

NAME=$1 PLAN=$2 WORKERS=$3 THREADS=$4 SCENARIO=$5 USERS=$6 SECONDS_TO_RUN=$7
case "$PLAN" in
  free) CPUS=0.1 MEM=512m ;;
  starter) CPUS=0.5 MEM=512m ;;
  standard) CPUS=1 MEM=2g ;;
  pro) CPUS=2 MEM=4g ;;
  *) echo "Unknown plan $PLAN" >&2; exit 2 ;;
esac
export LT_CPUS=$CPUS LT_MEM=$MEM LT_WORKERS=$WORKERS LT_THREADS=$THREADS LT_SCENARIO=$SCENARIO
# Capacity runs lift the per-user rate limits unless the caller sets them.
export LT_THROTTLE_ASK=${LT_THROTTLE_ASK:-100000/min} LT_THROTTLE_USER=${LT_THROTTLE_USER:-100000/min}
export LT_THROTTLE_SUGGEST=${LT_THROTTLE_SUGGEST:-100000/min}
export LT_OUT=/mnt/locust/results/$NAME
OUT=results/$NAME
rm -rf "$OUT" && mkdir -p "$OUT"

docker compose up -d --force-recreate --no-deps api >/dev/null 2>&1
for _ in $(seq 1 90); do
  curl -fsS http://127.0.0.1:8090/health/ready/ >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:8090/health/ready/ >/dev/null
docker compose exec -T db psql -q -U "$DB" -d "$DB" -c 'truncate chat_answercache' >/dev/null

# CPU, memory and database connections of the API, every 5 seconds.
(
  echo 'time,cpu_percent,memory,db_connections'
  while :; do
    stats=$(docker stats --no-stream --format '{{.CPUPerc}},{{.MemUsage}}' thapargenie-loadtest-api-1 2>/dev/null | sed 's/ \/.*//' || true)
    conns=$(docker compose exec -T db psql -At -U "$DB" -d "$DB" -c "select count(*) from pg_stat_activity where datname='$DB' and pid<>pg_backend_pid()" 2>/dev/null || true)
    echo "$(date +%H:%M:%S),$stats,$conns"
    sleep 5
  done
) > "$OUT/samples.csv" &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null || true' EXIT

SPAWN=$(( USERS / 10 > 0 ? USERS / 10 : 1 ))
docker compose run --rm -T locust -f locustfile.py --headless -H http://api:8000 \
  -u "$USERS" -r "$SPAWN" -t "${SECONDS_TO_RUN}s" --reset-stats --stop-timeout 20 \
  --csv "results/$NAME/locust" --only-summary > "$OUT/locust.log" 2>&1 || true

kill $SAMPLER 2>/dev/null || true
docker compose logs --no-color api > "$OUT/api.log" 2>&1 || true
docker inspect thapargenie-loadtest-api-1 --format '{{.State.OOMKilled}} {{.RestartCount}}' > "$OUT/state.txt"
cat > "$OUT/run.json" <<EOF
{"name": "$NAME", "plan": "$PLAN", "cpus": $CPUS, "memory": "$MEM", "workers": $WORKERS, "threads": $THREADS, "scenario": "$SCENARIO", "users": $USERS, "seconds": $SECONDS_TO_RUN, "throttle_ask": "$LT_THROTTLE_ASK"}
EOF
echo "done $NAME"
