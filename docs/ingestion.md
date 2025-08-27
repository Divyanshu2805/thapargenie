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
   written by the fast model. It only goes into the search text.
5. **Embed.** The search text (title, category, headings and the chunk) is embedded in
   batches of 50.
6. **Swap.** Old chunks are replaced by the new ones in one transaction, so a document
   stays answerable while it is reprocessed.

Failures leave the document `failed` with a message the admin can read. Anything left
`queued` or stuck in `processing` is picked up again by `python manage.py process_documents`
or by the recovery loop that runs in the server.

Documents can carry a "valid until" date. After it they are marked not current, which
lowers them in search; `python manage.py expire_documents` does this on demand.
