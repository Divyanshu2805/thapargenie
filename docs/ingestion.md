# Ingestion

Adding a document (`knowledge/services.py`) stores the original in the private bucket,
saves a row marked `queued` and hands it to a background thread (`knowledge/jobs.py`).
The work itself is in `knowledge/ingest/pipeline.py`:

1. **Claim.** The row moves from `queued` to `processing` in one update, so a document is
   never processed twice.
2. **Extract** (`ingest/extract.py`). The file type comes from the bytes, not the name.
   PDFs use their text layer; scans and pages with little text are read by the model in
   20-page windows ("smart" parsing, or forced per document). Word, Excel, CSV and HTML
   files and web pages are turned into Markdown, with tables kept as tables.
3. **Chunk** (`ingest/chunk.py`). Markdown is split along headings into chunks of about 450
   tokens with a little overlap. Tables are kept whole where possible and split by rows
   otherwise, each part repeating the header row.
4. **Context** (optional). One sentence per chunk saying where it sits in the document,
   written by the fast model, which reads up to 60,000 characters of the page. It only goes
   into the search text.
5. **Embed.** The search text (title, category, headings and the chunk) is embedded in
   batches of 50.
6. **Swap.** Old chunks are replaced by the new ones in one transaction, so a document
   stays answerable while it is reprocessed.

Failures leave the document `failed` with a message the admin can read. Anything left
`queued` or stuck in `processing` is picked up again by `python manage.py process_documents`
or by the recovery loop that runs in the server.

## Context for pages imported from the crawler

The crawler import keeps the crawler's chunks as they are, so by default they have no
context sentence. Two ways to add it:

- `python manage.py import_crawler_export <folder> --contextualize` writes the sentences as
  pages are imported (`--dry-run` shows how many fast-model calls that takes).
- `python manage.py contextualize_documents` adds them to pages already stored, without the
  export file: it reads each page once, writes a sentence for each chunk and re-embeds only
  those chunks. Run it with `--dry-run` first; `--limit` and `--title` allow a trial. It can
  be stopped (for example by the daily AI quota) and run again, and pages of more than 150
  chunks are skipped.

Documents can carry a "valid until" date. After it they are marked not current, which
lowers them in search; `python manage.py expire_documents` does this on demand.
