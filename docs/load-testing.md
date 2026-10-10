# Load testing

How many students one API instance can serve, measured for three instance sizes. The
harness is in [`loadtest/`](../loadtest/README.md); the figures below are from 36 runs on
2026-10-09 (102,194 requests, 11,164 streamed answers). Every run's raw numbers are in
[`assets/load-test-2026-10-09.csv`](assets/load-test-2026-10-09.csv).

## What was tested

The real API under the repository's `gunicorn.conf.py`, in a container limited to the CPU
and memory of a Render plan. Nothing talked to production, Firebase, Supabase or Gemini.

| Part | In the test |
|---|---|
| API | The current code, with CPU and memory limits per plan: free 0.1 CPU / 512 MB, starter 0.5 CPU / 512 MB, standard 1 CPU / 2 GB |
| Database | PostgreSQL 17 with pgvector, holding the crawled knowledge base: 1,341 documents, 12,666 passages |
| Network | A proxy adds 2 ms to every database round trip and 150 ms to every Firebase lookup |
| Sign-in | The Firebase Auth emulator, with 2,000 approved accounts |
| Models | A stand-in that takes as long as the real ones: 1.5 s for a structured call, 0.6 s for an embedding request, 5.5 s before the first word, 55 ms per word after it, each spread log-normally |
| Load | Locust 2.37, recording time to accepted, to the first word and to the full answer as separate measurements |

The stand-in matters: a request holds its worker thread and database connections for as
long as a real one, which is what limits capacity. With no load, the first word arrives in
about 8 s and the full answer in about 10 s, matching production.

Three scenarios:

| Scenario | Simulated student | Run length |
|---|---|---|
| `ask` | Asks one question after another with no pause, rate limits lifted. Users = answers streaming at once | 90 s |
| `browse` | Opens the app and reads old chats, 1 to 3 s apart. No questions | 60 s |
| `mix` | Opens the app, asks, reads for 20 to 60 s, looks at old chats, sometimes rates an answer or asks for follow-ups. Production rate limits | 5 min |

## What each size carries

"Students" means people using the app at the same moment, not registered accounts. With no
load at all, the first word takes about 8 seconds.

| Instance | Workers × threads | Answers streaming at once before requests queue | Mixed use |
|---|---|---|---|
| Free (0.1 CPU) | 2 × 8 | 8 (37 answers a minute, first word 8.6 s) | 100 students: nothing fails, but the first word takes 18 s and page loads take seconds |
| Starter (0.5 CPU) | 2 × 8 | 16 (74 a minute, first word 9.1 s) | 100 students: first word 11 s. 150 students: 28 s |
| Starter (0.5 CPU) | 2 × 16 | 32 (158 a minute, first word 8.3 s) | not run |
| Starter (0.5 CPU) | 2 × 32 | 64 (294 a minute, first word 8.6 s) | 400 students: 229 answers a minute, first word 9.1 s, no failures. 600 students: 22 s |
| Standard (1 CPU) | 2 × 32 | 64 (314 a minute, first word 8.3 s) | not run |
| Standard (1 CPU) | 4 × 32 | 128 (395 a minute, first word 11 s) | 1,000 students: first word 29 s, 1.6% of asks refused as busy |

Only three of the 36 runs had failed requests: the two that gave the free plan 32
threads per worker under heavy load, and the 1,000-student run.

## What limits it

**Threads first.** Each streaming answer holds one worker thread for about 10 seconds. With
16 threads, the 17th question waits for a free one: time to accepted jumps from 0.1 s to
several seconds while CPU sits idle. Throughput in answers per minute is close to
6 × threads until the CPU runs out.

| Starter, `ask` | Streams | Answers / min | Accepted p50 | First word p50 | CPU, share of one core |
|---|---|---|---|---|---|
| 2 × 8 | 16 | 74 | 0.13 s | 9.1 s | 10% |
| 2 × 8 | 24 | 85 | 2.3 s | 10 s | 12% |
| 2 × 16 | 32 | 158 | 0.10 s | 8.3 s | 18% |
| 2 × 32 | 64 | 294 | 0.33 s | 8.6 s | 27% |
| 2 × 32 | 96 | 325 | 1.7 s | 11 s | 31% |
| 2 × 64 | 128 | 322 | 3.9 s | 13 s | 45% |

**Then CPU.** Half a CPU tops out at about 320 answers a minute however many threads it is
given: 2 × 64 did no better than 2 × 32, with the CPU at 45% of a core against its 50%
allowance. One CPU with four workers reached about 410; that run shared one laptop with the
database and the load generator, so treat it as a floor. The free plan's tenth of a CPU is
the limit almost at once: giving it 32 threads per worker made it worse, with a quarter of
answers failing at 64 streams.

**Database connections.** Each thread keeps a connection and an open stream uses a second.

| Workers × threads | Peak connections |
|---|---|
| 2 × 8 | 39 |
| 2 × 16 | 72 |
| 2 × 32 | 136 |
| 4 × 32 | 262 |

A small Supabase plan allows 60 direct connections, so anything above 2 × 16 needs the
transaction pooler (`DATABASE_TRANSACTION_POOLING=true`). `check --deploy` warns about this.

**Memory.** Two workers stay between 210 and 350 MB. Four workers reach 560 MB, which does
not fit a 512 MB plan.

## Without the model

`browse` shows the plain API: authentication, the chat list, app state and notices.

| Instance | Students | Requests / s | p50 | p95 |
|---|---|---|---|---|
| Free | 25 | 10 | 1.5 s | 4.7 s |
| Starter | 50 | 50 | 21 ms | 87 ms |
| Starter | 100 | 74 | 322 ms | 1.4 s |
| Standard | 200 | 190 | 19 ms | 490 ms |
| Standard | 400 | 196 | 950 ms | 1.7 s |

A tenth of a CPU serves about 10 requests a second, half a CPU about 75 and one CPU about
195, on two workers of eight threads.

## The mix in full

| Instance | Workers × threads | Students | Answers / min | First word p50 / p95 | Full answer p50 / p95 | Failed | Other requests p95 |
|---|---|---|---|---|---|---|---|
| Free | 2 × 8 | 100 | 40 | 18 s / 31 s | 24 s / 37 s | 0% | 24 s |
| Starter | 2 × 8 | 100 | 53 | 11 s / 20 s | 13 s / 22 s | 0% | 10 s |
| Starter | 2 × 8 | 150 | 54 | 28 s / 44 s | 30 s / 46 s | 0% | 35 s |
| Starter | 2 × 8 | 200 | 58 | 35 s / 56 s | 35 s / 58 s | 0% | 49 s |
| Free | 2 × 32 | 300 | 16 | 46 s / 119 s | 76 s / 136 s | 11.8% | 60 s |
| Starter | 2 × 32 | 400 | 229 | 9.1 s / 23 s | 11 s / 25 s | 0% | 12 s |
| Starter | 2 × 32 | 600 | 220 | 22 s / 37 s | 24 s / 40 s | 0% | 27 s |
| Standard | 4 × 32 | 1,000 | 266 | 29 s / 54 s | 31 s / 56 s | 1.6% | 47 s |

In the 400-student run, 109 of 1,236 answers came from the answer cache.

When an instance is overloaded, ordinary page loads slow down with the answers, because
they wait for the same threads. That is the first thing a student would notice.

## What this means for production

- Production runs the free configuration, 2 × 8. It serves about 8 answers at once at full
  speed, and beyond that it slows down instead of failing.
- The cheapest real step is more threads on half a CPU with the transaction pooler: 2 × 32
  carried four times the students of 2 × 8 on the same plan.
- Beyond about 320 answers a minute the answer is CPU, and with four workers, memory.
- The daily AI budget (5,000 calls, roughly three per answered question) is reached long
  before any of these limits on a busy day. It is a deliberate spending cap, set in
  **Admin → Settings**.

## Limits of the test

- One laptop ran the API, the database and the load generator, so the larger runs compete
  for the same machine.
- The model is a timed stand-in. Real model latency varies more, and a real provider has
  its own rate limits.
- Simulated questions are mostly unique, so the answer cache helps less than it would with
  real students.
- Runs are short: 90 seconds to 5 minutes. No soak test was run.
- The free plan's CPU share is an approximation of a shared host.

To run it again, see [`loadtest/README.md`](../loadtest/README.md).
