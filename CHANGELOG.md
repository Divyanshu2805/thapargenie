# Changelog

## 2.0.0 (2025-08-28)

Search and answers
- Questions are analysed first: follow-ups are rewritten, greetings and off-topic questions
  get a short reply, and Thapar abbreviations are expanded.
- Hybrid search: vector and full-text results merged with reciprocal rank fusion, with small
  boosts for current documents and matching sessions.
- Optional reranking, neighbouring chunks pulled in when a passage is cut off, and duplicate
  passages dropped.
- Figures in an answer are checked against its sources; unverified answers are flagged.
- Rolling summary for long chats and a cache for repeated first questions.
- OpenAI as a second provider, scanned PDF reading, Excel/CSV/HTML files, and an optional
  context sentence per chunk.
- Golden questions and a nightly search quality check.

Students
- Pin, archive, search, export and delete all chats.
- Regenerate answers and edit questions, with a switcher between versions.
- Follow-up suggestions, voice input, "What can I ask?", notices, site feedback,
  printing, share links, and install as an app.
- A line saying how current an answer's sources are.

Admins
- Dashboard with usage charts, feedback review, knowledge gaps, playground, settings with
  maintenance mode, users and invitations, audit log and notices.
- Bulk document actions, chunk editing, valid-until dates, suggested sessions and dates,
  CSV exports.

Hardening
- Security headers and CSP, row level security, data retention, structured logs and error
  reports, end-to-end tests and CI.

## 1.0.0 (2025-05-22)

- Sign in with Firebase; admin approval for new accounts.
- Documents from uploads (PDF, Word), web pages and text, plus the crawler import.
- Vector search with pgvector and streamed answers with numbered citations.
- Saved conversations, answer feedback and a daily question limit.
- Settings page, privacy notice and an admin page for documents.
