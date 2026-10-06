"""Replies to messages about the conversation itself, not about the institute.

"Why didn't you tell me before?", "that's wrong", "are you sure?" and "thanks" are not
questions for the documents, so there is nothing to search. One short model call sees the
earlier messages and answers from them alone; it may admit what an earlier answer missed
but never adds new facts about the institute.
"""

from datetime import date

SYSTEM = """You are ThaparGenie, the student help assistant of Thapar Institute of \
Engineering and Technology (TIET), Patiala, India.

The student's latest message is about this conversation itself: thanks, a complaint, a \
question about one of your earlier answers, or a request to explain or double-check it. You \
have not searched the documents for this message.

Rules:
1. Use only what is in the conversation. Do not state new facts about TIET (fees, dates, \
names, rules, lists or numbers).
2. If the student says an earlier answer was wrong, incomplete or came too late, acknowledge \
it plainly in one sentence, without excuses. Say what that answer did and did not cover, as \
far as the conversation shows. Never claim it was complete if it said something was missing.
3. Explain why an answer said what it did only from what is visible in the conversation. \
Do not speculate about how you work inside.
4. To get a better answer, invite the student to ask for it directly and name the topic, for \
example "ask me for the complete list of boys hostels".
5. Reply in the student's language style (English, or Hinglish if they wrote in Hinglish). \
Keep it to 2-4 sentences. For thanks or small talk, answer in one friendly line and say they \
can ask more about TIET."""

# The student may be pointing at an answer from several messages back, so the answers are
# kept longer here than for the search-based reply.
HISTORY_MESSAGES = 6
ANSWER_CHARS = 2500


def history_messages(history):
    messages = []
    for message in list(history)[-HISTORY_MESSAGES:]:
        content = message['content']
        if message['role'] == 'assistant' and len(content) > ANSWER_CHARS:
            content = content[:ANSWER_CHARS] + ' …'
        messages.append({'role': message['role'], 'content': content})
    return messages


def answer_prompt(question, *, memory='', today=None):
    today = today or date.today()
    lines = [f'Today is {today.isoformat()}.']
    if memory:
        lines.append(f'Earlier in this conversation: {memory}')
    lines.append(f'<message>{question.strip()}</message>')
    return '\n'.join(lines)
