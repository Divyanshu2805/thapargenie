"""Summarise results/*/ into one table (Markdown on stdout, results/summary.csv on disk).

    python report.py
"""

import csv
import json
import re
from pathlib import Path

RESULTS = Path(__file__).parent / 'results'
ROWS = {'accepted': 'ask: accepted', 'first': 'ask: first word', 'full': 'ask: full answer',
        'all': 'Aggregated'}
NON_AI = re.compile(r'^(GET|POST conversations|PUT)')


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def megabytes(text):
    match = re.match(r'([\d.]+)\s*(GiB|MiB|KiB)', text or '')
    if not match:
        return 0.0
    return float(match.group(1)) * {'GiB': 1024, 'MiB': 1, 'KiB': 1 / 1024}[match.group(2)]


def read_run(folder):
    run = json.loads((folder / 'run.json').read_text())
    stats_file = folder / 'locust_stats.csv'
    if not stats_file.exists():
        return {**run, 'note': 'no results'}
    stats = {row['Name']: row for row in csv.DictReader(stats_file.open())}
    for key, name in ROWS.items():
        row = stats.get(name)
        if row:
            count, failed = number(row['Request Count']), number(row['Failure Count'])
            run[f'{key}_n'] = int(count)
            run[f'{key}_fail_pct'] = round(100 * failed / count, 1) if count else 0.0
            run[f'{key}_p50'] = int(number(row['50%']))
            run[f'{key}_p95'] = int(number(row['95%']))
            run[f'{key}_rps'] = round(number(row['Requests/s']), 2)
    # Everything that is not a streamed answer, weighted by request count.
    plain = [row for name, row in stats.items() if NON_AI.match(name)]
    count = sum(number(row['Request Count']) for row in plain)
    if count:
        run['plain_n'] = int(count)
        run['plain_fail_pct'] = round(
            100 * sum(number(row['Failure Count']) for row in plain) / count, 1)
        run['plain_p50'] = int(sum(number(r['50%']) * number(r['Request Count'])
                                   for r in plain) / count)
        run['plain_p95'] = int(max(number(row['95%']) for row in plain))
        run['plain_rps'] = round(sum(number(row['Requests/s']) for row in plain), 1)
    samples = list(csv.DictReader((folder / 'samples.csv').open()))
    cpu = [number((row['cpu_percent'] or '').rstrip('%')) for row in samples]
    run['cpu_avg_pct'] = round(sum(cpu) / len(cpu), 1) if cpu else 0
    run['cpu_max_pct'] = max(cpu, default=0)
    run['mem_max_mb'] = int(max((megabytes(row['memory']) for row in samples), default=0))
    run['db_conn_max'] = int(max((number(row['db_connections']) for row in samples), default=0))
    state = (folder / 'state.txt').read_text().split()
    run['oom_killed'] = state[0] == 'true'
    log = (folder / 'api.log').read_text(errors='replace')
    run['worker_timeouts'] = log.count('WORKER TIMEOUT')
    types = folder / 'answer_types.json'
    run['answer_types'] = json.loads(types.read_text()) if types.exists() else {}
    failures = folder / 'locust_failures.csv'
    if failures.exists():
        run['errors'] = '; '.join(f"{row['Error'][:40]} x{row['Occurrences']}"
                                  for row in csv.DictReader(failures.open()))[:160]
    return run


def seconds(run, key):
    value = run.get(key)
    return f'{value / 1000:.1f}' if value is not None else '-'


def main():
    folders = sorted(RESULTS.iterdir(), key=lambda p: p.stat().st_mtime)
    runs = [read_run(folder) for folder in folders if (folder / 'run.json').exists()]
    keys = sorted({key for run in runs for key in run if key != 'answer_types'})
    with (RESULTS / 'summary.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(runs)
    for scenario in ('ask', 'mix', 'browse'):
        chosen = [run for run in runs if run['scenario'] == scenario]
        if not chosen:
            continue
        print(f'\n### {scenario}\n')
        if scenario == 'browse':
            print('| plan | workers x threads | users | req/s | p50 ms | p95 ms | fail % '
                  '| CPU avg/max % | mem MB | DB conns |')
            print('|---|---|---|---|---|---|---|---|---|---|')
            for run in chosen:
                print(f"| {run['plan']} | {run['workers']}x{run['threads']} | {run['users']} "
                      f"| {run.get('plain_rps', '-')} | {run.get('plain_p50', '-')} "
                      f"| {run.get('plain_p95', '-')} | {run.get('plain_fail_pct', '-')} "
                      f"| {run.get('cpu_avg_pct')}/{run.get('cpu_max_pct')} "
                      f"| {run.get('mem_max_mb')} | {run.get('db_conn_max')} |")
            continue
        print('| plan | workers x threads | users | answers/min | accepted p50/p95 ms '
              '| first word p50/p95 s | full answer p50/p95 s | failed % | other API p95 ms '
              '| CPU avg/max % | mem MB | DB conns | notes |')
        print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for run in chosen:
            notes = [run.get('errors', '')]
            if run.get('oom_killed'):
                notes.append('OUT OF MEMORY')
            if run.get('worker_timeouts'):
                notes.append(f"{run['worker_timeouts']} worker timeouts")
            print(f"| {run['plan']} | {run['workers']}x{run['threads']} | {run['users']} "
                  f"| {round(run.get('full_rps', 0) * 60)} "
                  f"| {run.get('accepted_p50', '-')}/{run.get('accepted_p95', '-')} "
                  f"| {seconds(run, 'first_p50')}/{seconds(run, 'first_p95')} "
                  f"| {seconds(run, 'full_p50')}/{seconds(run, 'full_p95')} "
                  f"| {run.get('full_fail_pct', '-')} | {run.get('plain_p95', '-')} "
                  f"| {run.get('cpu_avg_pct')}/{run.get('cpu_max_pct')} "
                  f"| {run.get('mem_max_mb')} | {run.get('db_conn_max')} "
                  f"| {' '.join(n for n in notes if n)} |")


if __name__ == '__main__':
    main()
