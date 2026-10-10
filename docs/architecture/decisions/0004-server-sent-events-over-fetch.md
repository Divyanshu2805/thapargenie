# 0004. Server-sent events over fetch

## Context

A full answer takes about 10 seconds and must appear word by word. The browser must send a
bearer token and a JSON body with the request.

## Decision

The ask endpoints answer a `POST` with `text/event-stream`. The web app reads the
stream with `fetch`, not `EventSource`, because `EventSource` cannot send headers or a
body. The server sends a comment line every 15 seconds to keep proxies from closing an idle
connection.

## Consequences

- Plain HTTP: it passes through Render and Cloudflare with no special configuration.
- A dropped connection is detected on the server, which saves the partial answer as "stopped".
- Each open stream holds one worker thread, which is what bounds concurrent answers; see [load testing](../../load-testing.md).
- The request must also accept `application/json`, or content negotiation refuses it before the view runs.

## Alternatives considered

- **WebSockets**: two-way traffic that is not needed, and an ASGI server to run.
- **Polling**: slower to first word and more requests.
