# Load test

A local stack that runs the real API under load, sized like a Render plan. Nothing here
talks to production, Supabase, Firebase or Gemini. What it measured is in
[load testing](../docs/load-testing.md).

## What is in the box

| File | |
|---|---|
| `compose.yml` | The stack: database, Auth emulator, delay proxy, the API, a seeding job and Locust |
| `Dockerfile`, `emulator.Dockerfile` | The API with its locked requirements (the code is mounted, not copied), and the Firebase Auth emulator |
| `app/lt_wsgi.py` | Starts the real app and makes the offline model as slow as a real one, so threads and connections are held for a realistic time |
| `app/seed.py` | Migrates the database, creates the test accounts and lifts the daily limits. Refuses to run against anything but this stack |
| `locustfile.py` | The simulated students: `browse`, `ask` and `mix` |
| `up.sh` | Builds and starts the stack, sets the network delays, seeds it |
| `run.sh` | One run: restarts the API at a given size, runs Locust, keeps the results |
| `matrix.sh` | The full set of runs behind the published results |
| `report.py` | Turns `results/` into Markdown tables and `results/summary.csv` |
| `toxiproxy.json`, `empty.env`, `firebase.json` | Proxy routes, an empty `.env` mounted over the real one, and the emulator config |

## Running it

Needs Docker and a Bash shell (Git Bash on Windows).

```bash
cd loadtest

# once: build, start, seed. Give it the crawler export for a real knowledge base.
LT_EXPORT_DIR=/path/to/crawler-export ./up.sh

# one run: NAME PLAN WORKERS THREADS SCENARIO USERS SECONDS
./run.sh starter-2x8-ask16 starter 2 8 ask 16 90

# everything, skipping runs already done
./matrix.sh            # or: ./matrix.sh ask   ./matrix.sh browse   ./matrix.sh mix

python report.py       # tables on stdout, results/summary.csv on disk
docker compose down    # add -v to drop the database volume too
```

`PLAN` is `free` (0.1 CPU, 512 MB), `starter` (0.5 CPU, 512 MB), `standard` (1 CPU, 2 GB)
or `pro` (2 CPU, 4 GB). Results land in `results/<NAME>/`, which git ignores.

Without `LT_EXPORT_DIR` the knowledge base is empty and every answer is "not found": the
run still exercises threads and connections, but skips the larger prompts and the cache.

## Settings

| Variable | Default | |
|---|---|---|
| `LT_DB` | `thapargenie` | Name of the database, its user and password |
| `LT_ACCOUNTS` | `2000` | Test students to create and rotate through |
| `LT_DB_MS` | `2` | Delay added to every database round trip |
| `LT_FIREBASE_MS` | `150` | Delay added to every Firebase lookup |
| `LT_CALL_MS` | `1500` | Median time of a structured model call |
| `LT_EMBED_MS` | `600` | Median time of an embedding request |
| `LT_FIRST_WORD_MS` | `5500` | Median wait before the answer's first word |
| `LT_WORD_MS` | `55` | Per word after that |
| `LT_JITTER_SIGMA` | `0.35` | Spread of every delay; 0 makes them fixed |
| `LT_POPULAR_SHARE` | `0.15` | Share of questions asked word for word by many students, which the cache can answer |
| `LT_THROTTLE_ASK`, `LT_THROTTLE_USER`, `LT_THROTTLE_SUGGEST` | lifted by `run.sh` | Set them to the production values (`6/min`, `120/min`, `10/min`) to test with rate limits, as `matrix.sh mix` does |

## Reading a run

A streamed answer is reported as three rows:

| Row | Time until |
|---|---|
| `ask: accepted` | The server starts the stream: authentication, limits, saving the question. It rises first when threads run out |
| `ask: first word` | The first word of the answer arrives |
| `ask: full answer` | The answer is complete |

`samples.csv` holds the API's CPU, memory and database connections every 5 seconds;
`answer_types.json` counts how answers ended; `state.txt` says whether the container was
killed for memory.
