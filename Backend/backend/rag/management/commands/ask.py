import json

from django.core.management.base import BaseCommand

from rag.pipeline import answer_events


class Command(BaseCommand):
    help = 'Ask one question through the full pipeline and show how it was answered.'

    def add_arguments(self, parser):
        parser.add_argument('question')
        parser.add_argument('--rerank', action='store_true')
        parser.add_argument('--trace', action='store_true', help='Print retrieval details.')

    def handle(self, question, rerank, trace, **options):
        result = None
        for event, data in answer_events(question, rerank_enabled=rerank):
            if event == 'status':
                self.stderr.write(f'… {data["stage"]} {data.get("detail", "")}')
            elif event == 'delta':
                self.stdout.write(data['text'], ending='')
                self.stdout.flush()
            elif event == 'done':
                result = data
        self.stdout.write('\n')
        self.stdout.write(json.dumps(result.analysis.as_dict(), indent=2, ensure_ascii=False))
        for source in result.sources:
            mark = '*' if source.number in result.cited else ' '
            self.stdout.write(
                f' {mark}[{source.number}] {source.title} › {source.heading_path} '
                f'(p.{source.page_start or "-"}) {source.url}'
            )
        self.stdout.write(
            f'type={result.answer_type} model={result.model} '
            f'reranked={result.reranked} timings={result.timings}'
        )
        if trace:
            self.stdout.write(json.dumps(result.retrieval_trace, indent=2, ensure_ascii=False))
