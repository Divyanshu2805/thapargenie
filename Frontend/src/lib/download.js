// Saving a file the browser already holds (exports, CSVs, a chat as Markdown).

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The file name from a `Content-Disposition: attachment; filename="…"` header. */
export function filenameFrom(contentDisposition, fallback) {
  const match = /filename="?([^";]+)"?/i.exec(contentDisposition || '');
  return match ? match[1] : fallback;
}
