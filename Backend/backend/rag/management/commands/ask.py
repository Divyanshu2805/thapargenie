from django.core.management.base import BaseCommand

from rag.pipeline import answer_events


class Command(BaseCommand):
    help = 'Ask one question through the full pipeline and show how it was answered.'

    def add_arguments(self, parser):
        parser.add_argument('question')

    def handle(self, question, **options):
        result = None
        for event, data in answer_events(question):
            if event == 'status':
                self.stderr.write(f'… {data["stage"]} {data.get("detail", "")}')
            elif event == 'delta':
                self.stdout.write(data['text'], ending='')
                self.stdout.flush()
            elif event == 'done':
                result = data
        self.stdout.write('\n')
        for source in result.sources:
            mark = '*' if source.number in result.cited else ' '
            self.stdout.write(
                f' {mark}[{source.number}] {source.title} › {source.heading_path} '
                f'(p.{source.page_start or "-"}) {source.url}'
            )
        self.stdout.write(f'type={result.answer_type} model={result.model}')
