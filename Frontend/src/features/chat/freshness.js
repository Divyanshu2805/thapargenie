// How current the cited sources of an answer are: the sessions they cover, their latest
// date, and whether the student should double-check (a document marked not current, or
// nothing from the current session). Sessions run July to June, e.g. "2026-27".

const SESSION = /^\d{4}-\d{2}$/;
const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function currentSession(now = new Date()) {
  const start = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`;
}

// "2026-08-12" as a local date, so it never shifts a day across time zones.
function parseDate(value) {
  const match = DATE.exec(value || '');
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

function formatDay(date) {
  return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** "12 Aug 2026" for a source's effective_date, or null. */
export function formatSourceDate(value) {
  const date = parseDate(value);
  return date ? formatDay(date) : null;
}

/**
 * Returns null when there is nothing worth saying, otherwise
 * {summary: string|null, warning: string|null}.
 */
export function describeFreshness(sources, now = new Date()) {
  const cited = (sources || []).filter((source) => source.cited);
  if (!cited.length) return null;

  const sessions = [...new Set(cited.map((s) => s.academic_year).filter((y) => SESSION.test(y || '')))].sort();
  // A date after today is not when the document was issued (imported pages carry
  // placeholders such as 31 Dec 2027), so it is left out.
  const dates = cited
    .map((s) => parseDate(s.effective_date))
    .filter((date) => date && date <= now)
    .sort((a, b) => a - b);
  const latest = dates.at(-1);

  const parts = [];
  if (sessions.length) {
    parts.push(`Based on session${sessions.length > 1 ? 's' : ''} ${sessions.join(', ')} sources`);
  }
  if (latest) {
    const dated = `${dates.length > 1 ? 'latest dated' : 'dated'} ${formatDay(latest)}`;
    parts.push(parts.length ? dated : `Sources ${dated}`);
  }
  const summary = parts.length ? parts.join(' · ') : null;

  let warning = null;
  const session = currentSession(now);
  const newest = sessions.at(-1);
  if (cited.some((source) => source.is_current === false)) {
    warning = 'One of these sources is marked as no longer current. Check the latest official notice before relying on this answer.';
  } else if (newest && newest < session) {
    warning = `The newest source is from session ${newest}. Details for ${session} may differ; check the official site.`;
  }

  return summary || warning ? { summary, warning } : null;
}
