import time

from django.core.management.base import BaseCommand, CommandError

from rag import evaluation, quality
from rag.llm import get_llm


class Command(BaseCommand):
    help = 'Score retrieval (and optionally answers) against rag/eval/golden.json.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(evaluation.GOLDEN))
        parser.add_argument('--case', action='append', help='Only run this case id (repeatable).')
        parser.add_argument('--rerank', action='store_true',
                            help='Rerank candidates with the fast model before answering.')
        parser.add_argument('--answers', action='store_true',
                            help='Also generate full answers (more LLM calls).')
        parser.add_argument('--min-recall', type=float, default=0.9,
                            help='Fail if recall@5 is below this (default 0.9).')
        parser.add_argument('--record', choices=('nightly', 'manual'),
                            help='Save the run for the admin Overview (search quality only).')

    def handle(self, file, case, rerank, answers, min_recall, record=None, **options):
        if record and (answers or case):
            raise CommandError('--record scores the full set, search quality only: '
                               'drop --answers and --case.')
        cases = evaluation.load_cases(file, only=set(case or []))
        if not cases:
            raise CommandError('No cases selected.')
        llm = get_llm()

        def show(result):
            case = result.case
            if result.error:
                status = self.style.ERROR(f'ERROR {result.error}')
            elif not case['expected']:
                status = f'intent={result.intent}'
                if result.intent_ok is not None:
                    status += ' (ok)' if result.intent_ok else self.style.ERROR(' (WRONG)')
                if result.list_complete is not None:
                    if result.list_complete:
                        status = self.style.SUCCESS('whole list in sources')
                    else:
                        status = self.style.ERROR('list INCOMPLETE in sources')
            elif result.rank and result.rank <= 5:
                status = self.style.SUCCESS(f'rank {result.rank}')
            elif result.rank:
                status = self.style.WARNING(f'rank {result.rank}')
            else:
                status = self.style.ERROR('miss')
            extra = ''
            if result.source_hit is not None:
                extra += ' | in sources' if result.source_hit else ' | NOT in sources'
            if result.answer_type:
                mark = 'ok' if result.answer_ok else 'WRONG'
                extra += f' | answer={result.answer_type} ({mark})'
                if result.grounded is False:
                    extra += ' | UNGROUNDED'
            self.stdout.write(f'{case["id"]:<40} {status}{extra}')
            if result.standalone and result.standalone != case['question']:
                self.stdout.write(f'{"":<40}   -> {result.standalone}')

        started = time.monotonic()
        report = evaluation.run(
            llm, cases, use_rerank=rerank, with_answers=answers, on_result=show
        )
        self.stdout.write('')
        self.stdout.write(f'recall@5   {report.recall(5):.2f}')
        self.stdout.write(f'recall@10  {report.recall(10):.2f}')
        self.stdout.write(f'MRR        {report.mrr():.2f}')
        if report.source_hit_rate() is not None:
            self.stdout.write(f'in sources {report.source_hit_rate():.2f}')
        if report.list_completeness() is not None:
            self.stdout.write(f'full lists {report.list_completeness():.2f}')
        if report.intent_accuracy() is not None:
            self.stdout.write(f'intents    {report.intent_accuracy():.2f}')
        if report.answer_accuracy() is not None:
            self.stdout.write(f'answers    {report.answer_accuracy():.2f}')
        self.stdout.write(f'LLM calls  {llm.usage.calls}')
        if record:
            run = quality.record(report, llm, trigger=record,
                                 duration_ms=int((time.monotonic() - started) * 1000))
            self.stdout.write(f'recorded   run {run.pk}')
        misses = report.important_misses()
        if misses:
            self.stdout.write(self.style.WARNING(f'important misses: {", ".join(misses)}'))
        if report.recall(5) < min_recall:
            raise CommandError(f'recall@5 {report.recall(5):.2f} is below {min_recall:.2f}.')
