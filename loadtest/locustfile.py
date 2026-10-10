"""Load generator for the ThaparGenie API.

LT_SCENARIO picks what the simulated students do:
  browse  page loads and reading old chats only, 1-3 s apart (no questions)
  ask     one question after another with no pause: users = answers streaming at once
  mix     a student using the app: opens it, asks, reads for 20-60 s, looks at old chats

A streamed answer is reported as three rows:
  ask: accepted    time until the server starts the stream (auth, quota, saving the turn)
  ask: first word  time until the first word of the answer arrives
  ask: full answer time until the answer is complete
"""

import itertools
import json
import os
import random
import time
import uuid

import requests
from locust import HttpUser, between, constant, events, task

EMULATOR = os.getenv('LT_EMULATOR', 'http://emulator:9099')
PASSWORD = 'Loadtest-only-password-1!'  # noqa: S105 - emulator accounts only
ACCOUNTS = int(os.getenv('LT_ACCOUNTS', '2000'))
SCENARIO = os.getenv('LT_SCENARIO', 'mix')
POPULAR_SHARE = float(os.getenv('LT_POPULAR_SHARE', '0.15'))
OUT = os.getenv('LT_OUT', '')
API = '/api/v1/'

# Asked word for word by many students: after the first answer these come from the cache.
POPULAR = [
    'What is the hostel fee for first year students?',
    'When does the odd semester start?',
    'What is the fee structure for BE computer engineering?',
    'How do I apply for a merit scholarship?',
    'What is the minimum attendance required to sit in exams?',
    'What are the library timings?',
    'How can I get a bonafide certificate?',
    'What is the last date to pay the semester fee?',
    'What are the hostel mess timings?',
    'How do I apply for a branch change?',
]
OPENERS = ['What is the', 'Tell me about the', 'How do I find the', 'Where can I read the',
           'Who handles the', 'When is the', 'Explain the', 'What are the rules for the']
TOPICS = ['hostel', 'mess', 'fee', 'scholarship', 'admission', 'cutoff', 'placement',
          'internship', 'syllabus', 'timetable', 'examination', 'attendance', 'library',
          'calendar', 'registration', 'refund', 'transcript', 'certificate', 'faculty',
          'department', 'laboratory', 'project', 'thesis', 'convocation', 'backlog',
          'grading', 'credit', 'elective', 'minor', 'exchange', 'medical', 'sports',
          'transport', 'wifi', 'anti-ragging', 'discipline', 'leave', 'stipend', 'loan',
          'migration', 'eligibility', 'counselling', 'withdrawal', 'reappear', 'summer']
DETAILS = ['for BE students', 'for ME students', 'for MBA students', 'for PhD scholars',
           'in the first year', 'in the final year', 'for the current session',
           'at the Patiala campus', 'at the Derabassi campus', 'for international students',
           'for lateral entry', 'for the electrical department', 'for the civil department',
           'for the mechanical department', 'for computer engineering', 'for biotechnology',
           'this semester', 'next semester', 'for hostellers', 'for day scholars']

_numbers = itertools.count(random.randrange(ACCOUNTS))  # noqa: S311
answer_types = {}


def question():
    if random.random() < POPULAR_SHARE:  # noqa: S311
        return random.choice(POPULAR)  # noqa: S311
    first, second = random.sample(TOPICS, 2)
    return (f'{random.choice(OPENERS)} {first} {second} policy '  # noqa: S311
            f'{random.choice(DETAILS)}?')  # noqa: S311


def find(data, key):
    """The first value stored under `key` anywhere in a JSON document."""
    if isinstance(data, dict):
        if key in data:
            return data[key]
        data = list(data.values())
    if isinstance(data, list):
        for item in data:
            found = find(item, key)
            if found is not None:
                return found
    return None


class Student(HttpUser):
    abstract = True

    def on_start(self):
        email = f'lt{next(_numbers) % ACCOUNTS:05d}@loadtest.example'
        response = requests.post(
            f'{EMULATOR}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',
            params={'key': 'loadtest'},
            json={'email': email, 'password': PASSWORD, 'returnSecureToken': True},
            timeout=30,
        )
        response.raise_for_status()
        self.client.headers['Authorization'] = f'Bearer {response.json()["idToken"]}'
        self.conversation = None
        self.conversations = []
        self.last_answer = None
        self.open_app()

    # -- what the web app does ----------------------------------------------------------

    def get(self, path, name=None):
        return self.client.get(API + path, name=name or f'GET {path}', timeout=60)

    def open_app(self):
        self.get('me/')
        self.get('app-config/')
        self.load_conversations()
        self.get('notices/')

    def load_conversations(self):
        response = self.get('conversations/')
        if response.status_code == 200:
            data = response.json()
            rows = data.get('results', data) if isinstance(data, dict) else data
            self.conversations = [row['id'] for row in rows]

    def open_conversation(self):
        if not self.conversations:
            self.load_conversations()
        if self.conversations:
            chosen = random.choice(self.conversations)  # noqa: S311
            self.get(f'conversations/{chosen}/messages/', 'GET conversations/<id>/messages/')

    def report(self, name, started, error=None):
        self.environment.events.request.fire(
            request_type='SSE', name=name, response_time=(time.perf_counter() - started) * 1000,
            response_length=0, exception=error, context={},
        )

    def ask(self):
        if self.conversation is None or random.random() < 0.5:  # noqa: S311
            created = self.client.post(API + 'conversations/', json={},
                                       name='POST conversations/', timeout=60)
            if created.status_code != 201:
                return
            self.conversation = created.json()['id']
        started = time.perf_counter()
        first_word = None
        error = None
        try:
            with self.client.post(
                f'{API}conversations/{self.conversation}/messages/',
                json={'content': question(), 'client_request_id': str(uuid.uuid4())},
                name='ask: accepted', stream=True, catch_response=True, timeout=(30, 180),
            ) as response:
                if response.status_code != 200:
                    code = find(response.json(), 'code') if response.content else None
                    error = f'{response.status_code} {code or ""}'.strip()
                    response.failure(error)
                else:
                    response.success()
                    event = None
                    for line in response.iter_lines(decode_unicode=True):
                        if line.startswith('event:'):
                            event = line[6:].strip()
                        elif line.startswith('data:') and event in ('delta', 'done', 'error'):
                            if event == 'delta' and first_word is None:
                                first_word = time.perf_counter()
                                self.report('ask: first word', started)
                            elif event == 'done':
                                done = json.loads(line[5:])
                                kind = find(done, 'answer_type') or 'unknown'
                                answer_types[kind] = answer_types.get(kind, 0) + 1
                                self.last_answer = find(done, 'id')
                                break
                            elif event == 'error':
                                error = f'stream error {find(json.loads(line[5:]), "code")}'
                                break
                    else:
                        error = 'stream ended early'
        except requests.RequestException as exc:
            error = type(exc).__name__
        if error:
            self.conversation = None
            if first_word is None:
                self.report('ask: first word', started, Exception(error))
        self.report('ask: full answer', started, Exception(error) if error else None)

    def after_answer(self):
        """The web app refreshes the chat list; some students rate or ask for follow-ups."""
        self.load_conversations()
        if not self.last_answer:
            return
        roll = random.random()  # noqa: S311
        if roll < 0.10:
            self.client.put(f'{API}messages/{self.last_answer}/feedback/', json={'rating': 1},
                            name='PUT messages/<id>/feedback/', timeout=60)
        elif roll < 0.18:
            self.client.post(f'{API}messages/{self.last_answer}/suggestions/', json={},
                             name='POST messages/<id>/suggestions/', timeout=60)


class Browser(Student):
    abstract = SCENARIO != 'browse'
    wait_time = between(1, 3)

    @task(3)
    def read_old_chat(self):
        self.open_conversation()

    @task(2)
    def reload(self):
        self.open_app()


class Asker(Student):
    abstract = SCENARIO != 'ask'
    wait_time = constant(0)

    @task
    def question(self):
        self.ask()


class ActiveStudent(Student):
    abstract = SCENARIO != 'mix'
    wait_time = between(20, 60)

    @task(5)
    def question(self):
        self.ask()
        self.after_answer()

    @task(3)
    def read_old_chat(self):
        self.open_conversation()

    @task(2)
    def reload(self):
        self.open_app()


@events.test_stop.add_listener
def save_answer_types(environment, **kwargs):
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, 'answer_types.json'), 'w') as handle:
            json.dump(answer_types, handle)
