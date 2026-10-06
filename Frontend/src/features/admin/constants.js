// Labels for the API's enum values (knowledge/models.py, chat/models.py, userauths/models.py).

export const CATEGORIES = [
  { value: 'admissions', label: 'Admissions' },
  { value: 'fees_scholarships', label: 'Fees & scholarships' },
  { value: 'hostel_campus_life', label: 'Hostels & campus life' },
  { value: 'academic_calendar', label: 'Academic calendar' },
  { value: 'courses_syllabus', label: 'Courses & syllabus' },
  { value: 'rules_regulations', label: 'Rules & regulations' },
  { value: 'departments', label: 'Departments' },
  { value: 'faculty', label: 'Faculty' },
  { value: 'placements', label: 'Placements' },
  { value: 'notices', label: 'Notices' },
  { value: 'about_contact', label: 'About & contact' },
  { value: 'faq', label: 'FAQ' },
  { value: 'other', label: 'Other' },
];

export const DOCUMENT_STATUSES = [
  { value: 'queued', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'ready', label: 'Ready' },
  { value: 'failed', label: 'Failed' },
  { value: 'disabled', label: 'Disabled' },
];

export const SOURCE_TYPES = {
  pdf: 'PDF',
  docx: 'Word',
  xlsx: 'Excel',
  csv: 'CSV',
  html: 'HTML file',
  url: 'Web page',
  text: 'Text / FAQ',
  crawler: 'Crawler import',
};

export const PARSERS = [
  { value: 'auto', label: 'Auto' },
  { value: 'fast', label: 'Fast (text layer)' },
  { value: 'smart', label: 'Smart (OCR + tables)' },
];

export const ANSWER_TYPES = {
  answered: 'Answered',
  cached: 'Cached answer',
  no_answer: 'Not found',
  smalltalk: 'Small talk',
  conversation: 'About the chat',
  out_of_scope: 'Out of scope',
  personal_record: 'Personal record',
  error: 'Error',
};

export const FEEDBACK_REASONS = {
  incorrect: 'Incorrect',
  outdated: 'Outdated',
  incomplete: 'Incomplete',
  irrelevant: 'Not what was asked',
  unclear: 'Hard to understand',
  other: 'Other',
};

export const ELIGIBILITY_STATES = {
  pending: 'Pending review',
  approved: 'Approved',
  denied: 'Denied',
  suspended: 'Suspended',
};

// Matches knowledge/services.py EXPIRY_WARNING_DAYS.
export const EXPIRY_WARNING_DAYS = 30;

export const VALIDITY_FILTERS = [
  { value: 'expiring', label: `Expiring in ${EXPIRY_WARNING_DAYS} days` },
  { value: 'expired', label: 'Past "valid until"' },
];

export const DETAILS_FILTERS = [{ value: 'missing_session', label: 'Missing session (time-sensitive)' }];

function localDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
  return match ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}

/**
 * A document's "valid until" state for badges: null when it has no date or the date is
 * more than EXPIRY_WARNING_DAYS away, else {state: 'expiring'|'expired', label}.
 */
export function validityOf(document, now = new Date()) {
  const until = localDate(document?.valid_until);
  if (!until) return null;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const day = until.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  if (until < today) return { state: 'expired', label: `Expired ${day}` };
  const daysLeft = Math.round((until - today) / 86_400_000);
  return daysLeft <= EXPIRY_WARNING_DAYS ? { state: 'expiring', label: `Expires ${day}` } : null;
}

export const labelOf = (list, value) => list.find((item) => item.value === value)?.label ?? value ?? '—';

/** Documents still moving through the pipeline; lists poll while any exist. */
export const isInFlight = (document) => document?.status === 'queued' || document?.status === 'processing';
