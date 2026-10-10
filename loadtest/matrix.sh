#!/usr/bin/env bash
# The full set of runs. Finished runs are skipped, so it can be restarted.
#   ./matrix.sh [ask|browse|mix ...]   (default: all three)
set -uo pipefail
cd "$(dirname "$0")"

run() {  # name plan workers threads scenario users seconds
  if [ -f "results/$1/run.json" ]; then echo "skip $1"; return; fi
  bash run.sh "$@" || echo "FAILED $1"
}

ask() {
  # Answers streaming at once, no pauses, rate limits lifted: where does each size stop?
  for users in 8 16 24; do run "ask-free-2x8-u$users" free 2 8 ask $users 90; done
  run ask-free-2x16-u32 free 2 16 ask 32 90
  run ask-free-2x32-u64 free 2 32 ask 64 90
  for users in 8 16 24 32; do run "ask-starter-2x8-u$users" starter 2 8 ask $users 90; done
  for users in 16 32 48; do run "ask-starter-2x16-u$users" starter 2 16 ask $users 90; done
  for users in 32 64 96; do run "ask-starter-2x32-u$users" starter 2 32 ask $users 90; done
  run ask-starter-2x64-u128 starter 2 64 ask 128 90
  for users in 64 96; do run "ask-standard-2x32-u$users" standard 2 32 ask $users 90; done
  for users in 128 192; do run "ask-standard-4x32-u$users" standard 4 32 ask $users 90; done
}

browse() {
  # Page loads and old chats only (no AI): the plain API under pressure.
  for users in 25 50 100; do run "browse-free-2x8-u$users" free 2 8 browse $users 60; done
  for users in 50 100 200; do run "browse-starter-2x8-u$users" starter 2 8 browse $users 60; done
  for users in 200 400; do run "browse-standard-2x8-u$users" standard 2 8 browse $users 60; done
}

mix() {
  # Students using the app, with the production rate limits (6 questions a minute each).
  export LT_THROTTLE_ASK=6/min LT_THROTTLE_USER=120/min LT_THROTTLE_SUGGEST=10/min
  run mix-free-2x8-u100 free 2 8 mix 100 300
  for users in 100 150 200; do run "mix-starter-2x8-u$users" starter 2 8 mix $users 300; done
  run mix-free-2x32-u300 free 2 32 mix 300 300
  for users in 400 600; do run "mix-starter-2x32-u$users" starter 2 32 mix $users 300; done
  run mix-standard-4x32-u1000 standard 4 32 mix 1000 300
  unset LT_THROTTLE_ASK LT_THROTTLE_USER LT_THROTTLE_SUGGEST
}

for stage in "${@:-ask browse mix}"; do
  for name in $stage; do "$name"; done
done
echo "matrix finished"
