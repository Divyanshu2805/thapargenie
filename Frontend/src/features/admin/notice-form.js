// Form state for the notice dialog, and how it maps to the API.
// Dates are the admin's local time; an expiry date means the end of that day.

export const MAX_TITLE = 160;
export const MAX_BODY = 5000;

function pad(number) {
  return String(number).padStart(2, '0');
}

function localDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function localTime(date) {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function at(dateText, timeText) {
  const [year, month, day] = dateText.split('-').map(Number);
  const [hours, minutes, seconds = 0] = timeText.split(':').map(Number);
  return new Date(year, month - 1, day, hours, minutes, seconds);
}

export const endOfDay = (dateText) => at(dateText, '23:59:59');

export function emptyForm() {
  return {
    title: '',
    body: '',
    category: 'notices',
    important: false,
    is_pinned: false,
    schedule: false,
    publish_date: '',
    publish_time: '09:00',
    expires_on: '',
    link_url: '',
    answerable: true,
  };
}

export function formFromNotice(notice) {
  const publish = new Date(notice.publish_at);
  return {
    title: notice.title,
    body: notice.body || '',
    category: notice.category,
    important: notice.importance === 'important',
    is_pinned: notice.is_pinned,
    schedule: notice.state === 'scheduled',
    publish_date: localDate(publish),
    publish_time: localTime(publish),
    expires_on: notice.expires_at ? localDate(new Date(notice.expires_at)) : '',
    link_url: notice.link_url || '',
    answerable: notice.answerable,
  };
}

/** Field errors for a save; `draft` saves skip nothing but the future-time checks still apply. */
export function validateNotice(form, now = new Date(), original = null) {
  const errors = {};
  const title = form.title.trim();
  if (!title) errors.title = 'Give the notice a title.';
  else if (title.length > MAX_TITLE) errors.title = `Keep the title under ${MAX_TITLE} characters.`;
  if (form.body.length > MAX_BODY) errors.body = `Keep it under ${MAX_BODY.toLocaleString('en-IN')} characters.`;
  if (form.link_url.trim() && !form.link_url.trim().startsWith('https://')) errors.link_url = 'Only https links are allowed.';

  let publishAt = now;
  if (form.schedule) {
    if (!form.publish_date || !form.publish_time) errors.publish = 'Pick a date and time.';
    else {
      publishAt = at(form.publish_date, form.publish_time);
      if (publishAt <= now) errors.publish = 'Pick a time in the future, or turn off scheduling.';
    }
  } else if (original && original.state !== 'scheduled') {
    publishAt = new Date(original.publish_at);
  }
  const expiryChanged = !original || form.expires_on !== formFromNotice(original).expires_on;
  if (form.expires_on && expiryChanged) {
    const expires = endOfDay(form.expires_on);
    if (expires <= now) errors.expires_on = 'The expiry must be today or later.';
    else if (expires <= publishAt) errors.expires_on = 'The expiry must be after the publish time.';
  }
  return errors;
}

/** The request body. `original` is the notice being edited, if any. */
export function toPayload(form, { draft, original = null }) {
  const body = {
    title: form.title.trim(),
    body: form.body.trim(),
    category: form.category,
    importance: form.important ? 'important' : 'normal',
    is_pinned: form.is_pinned,
    is_draft: draft,
    link_url: form.link_url.trim(),
    answerable: form.answerable,
  };
  if (form.schedule) body.publish_at = at(form.publish_date, form.publish_time).toISOString();
  // Turning scheduling off on a scheduled notice publishes it now.
  else if (original?.state === 'scheduled') body.publish_at = null;
  if (!original || form.expires_on !== formFromNotice(original).expires_on) {
    body.expires_at = form.expires_on ? endOfDay(form.expires_on).toISOString() : null;
  }
  return body;
}
