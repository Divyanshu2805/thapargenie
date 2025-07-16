import statistics

from django.core.management.base import BaseCommand, CommandError

from rag import evaluation
from rag.llm import get_llm
from rag.pipeline import answer_events

STAGES = ('analysis', 'embedding', 'retrieval', 'context', 'first_token', 'total')


def _percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(share * (len(ordered) - 1)))]


class Command(BaseCommand):
    help = ('Time the answer pipeline on the evaluation questions (no cache): p50/p90 per '
            'stage and to the first answer word. About 3 AI calls per question.')

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(evaluation.GOLDEN))
        parser.add_argument('--limit', type=int, default=10, help='Questions to time.')
        parser.add_argument('--warmup', type=int, default=1,
                            help='Untimed questions first (connections, model warm-up).')

    def handle(self, file, limit, warmup, **options):
        cases = [case for case in evaluation.load_cases(file) if case['expected']]
        if not cases:
            raise CommandError('No answerable cases found.')
        cases = cases[:warmup + limit]
        llm = get_llm()
        timings = []
        for index, case in enumerate(cases):
            result = None
            for event, data in answer_events(case['question'], llm=llm):
                if event == 'done':
                    result = data
            if index < warmup:
                continue
            timings.append(result.timings)
            first = result.timings.get('first_token', '-')
            self.stdout.write(f'{case["id"]:<40} first word {first} ms, '
                              f'total {result.timings["total"]} ms')

        self.stdout.write('')
        self.stdout.write(f'{"stage":<12} {"p50":>7} {"p90":>7}   (ms, {len(timings)} questions)')
        for stage in STAGES:
            values = [t[stage] for t in timings if stage in t]
            if values:
                self.stdout.write(f'{stage:<12} {statistics.median(values):>7.0f} '
                                  f'{_percentile(values, 0.9):>7.0f}')
        self.stdout.write(f'AI calls   {llm.usage.calls}')
