// Admin API, mounted at /api/v1/admin/. Every endpoint needs staff.
import { apiBlobRequest, apiRequest } from '../../utils/apiClient';
import { uploadRequest } from '../http';

export const adminKeys = {
  stats: (range) => ['admin', 'stats', range],
  documents: (filters = {}) => ['admin', 'documents', filters],
  document: (id) => ['admin', 'document', id],
  chunks: (id) => ['admin', 'document', id, 'chunks'],
  feedback: (filters = {}) => ['admin', 'feedback', filters],
  siteFeedback: (filters = {}) => ['admin', 'site-feedback', filters],
  notices: (filters = {}) => ['admin', 'notices', filters],
  gaps: (range) => ['admin', 'gaps', range],
  complaints: (range) => ['admin', 'complaints', range],
  settings: ['admin', 'settings'],
  invitations: (q) => ['admin', 'invitations', q],
  users: (filters = {}) => ['admin', 'users', filters],
  auditLog: (filters = {}) => ['admin', 'audit-log', filters],
  twoFactor: ['admin', 'two-factor'],
};

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

const admin = (path, options) => apiRequest(`admin/${path}`, options);

export const getStats = (range = '7d') => admin(`stats/${query({ range })}`);

export const listDocuments = ({ status, category, sourceType, validity, details, q, cursor } = {}) =>
  admin(`documents/${query({ status, category, source_type: sourceType, validity, details, q, cursor })}`);
// Every id matching the list's filters (≤ 2,000), for "select all matching".
export const listMatchingDocumentIds = ({ status, category, sourceType, validity, details, q } = {}) =>
  admin(`documents/ids/${query({ status, category, source_type: sourceType, validity, details, q })}`);
export const getDocument = (id) => admin(`documents/${id}/`);
export const updateDocument = (id, changes) => admin(`documents/${id}/`, { method: 'PATCH', body: changes });
export const deleteDocument = (id) => admin(`documents/${id}/`, { method: 'DELETE' });
export const reprocessDocument = (id, body = {}) => admin(`documents/${id}/reprocess/`, { method: 'POST', body });
export const enableDocument = (id) => admin(`documents/${id}/enable/`, { method: 'POST' });
export const disableDocument = (id) => admin(`documents/${id}/disable/`, { method: 'POST' });
export const getDocumentFileUrl = (id) => admin(`documents/${id}/file/`);
// Up to 100 documents, one at a time on the server: allow longer than the 10 s default.
export const bulkDocuments = ({ action, ids, changes, changesById }) =>
  admin('documents/bulk/', {
    method: 'POST',
    body: { action, ids, ...(changes ? { changes } : {}), ...(changesById ? { changes_by_id: changesById } : {}) },
    timeoutMs: 120_000,
  });
// Suggested session/date per document; nothing is saved. `ai` asks the model too.
export const suggestDetails = ({ ids, ai = false }) =>
  admin('documents/suggest-details/', { method: 'POST', body: { ids, ai }, timeoutMs: 120_000 });
export const listChunks = (id, cursor) => admin(`documents/${id}/chunks/${query({ cursor })}`);
export const updateChunk = (id, changes) => admin(`chunks/${id}/`, { method: 'PATCH', body: changes });
export const deleteChunk = (id) => admin(`chunks/${id}/`, { method: 'DELETE' });

/** `files` is a FileList or array; `metadata` holds the shared form fields. */
export function uploadDocuments(files, metadata = {}, { signal } = {}) {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  for (const [key, value] of Object.entries(metadata)) {
    if (value !== undefined && value !== null && value !== '') form.append(key, String(value));
  }
  return uploadRequest('admin/documents/', form, { signal });
}
export const addDocumentFromUrl = (body) => admin('documents/url/', { method: 'POST', body, timeoutMs: 30_000 });
export const addDocumentFromText = (body) => admin('documents/text/', { method: 'POST', body });

export const runPlayground = (body) => admin('playground/', { method: 'POST', body, timeoutMs: 90_000 });

export const listFeedback = ({ reviewStatus, rating, answerType, reason, cursor } = {}) =>
  admin(`feedback/${query({ review_status: reviewStatus, rating, answer_type: answerType, reason, cursor })}`);
export const updateFeedback = (id, changes) => admin(`feedback/${id}/`, { method: 'PATCH', body: changes });

export const listSiteFeedback = ({ reviewStatus, kind, cursor } = {}) =>
  admin(`site-feedback/${query({ review_status: reviewStatus, kind, cursor })}`);
export const updateSiteFeedback = (id, changes) => admin(`site-feedback/${id}/`, { method: 'PATCH', body: changes });

// Notices. DELETE needs a recent sign-in.
export const listAdminNotices = ({ state, q, cursor } = {}) => admin(`notices/${query({ state, q, cursor })}`);
export const createNotice = (body) => admin('notices/', { method: 'POST', body });
export const updateNotice = (id, changes) => admin(`notices/${id}/`, { method: 'PATCH', body: changes });
export const deleteNotice = (id, { deleteDocument = false } = {}) =>
  admin(`notices/${id}/${query({ delete_document: deleteDocument ? 'true' : undefined })}`, { method: 'DELETE' });

export const listGaps = (range = '30d') => admin(`gaps/${query({ range })}`);
export const listComplaints = (range = '30d') => admin(`complaints/${query({ range })}`);

// CSV downloads: same filters as the lists, at most 5,000 rows.
const adminCsv = (path) => apiBlobRequest(`admin/${path}`, { timeoutMs: 60_000 });
export const exportFeedbackCsv = ({ reviewStatus, rating, answerType, reason } = {}) =>
  adminCsv(`feedback/export/${query({ review_status: reviewStatus, rating, answer_type: answerType, reason })}`);
export const exportGapsCsv = (range = '30d') => adminCsv(`gaps/export/${query({ range })}`);
export const exportStatsCsv = (range = '7d') => adminCsv(`stats/export/${query({ range })}`);

// The second sign-in step for staff (features/admin/TwoFactorGate.jsx).
export const getTwoFactorStatus = () => admin('two-factor/');
export const setUpTwoFactor = () => admin('two-factor/setup/', { method: 'POST' });
export const confirmTwoFactor = (code) => admin('two-factor/confirm/', { method: 'POST', body: { code: code.trim() } });
// `body` is { code } from the app or { recovery_code } from the saved backup codes.
export const verifyTwoFactor = (body) => admin('two-factor/verify/', { method: 'POST', body });
export const newRecoveryCodes = () => admin('two-factor/recovery-codes/', { method: 'POST' });

export const getSettings = () => admin('settings/');
export const updateSettings = (changes) => admin('settings/', { method: 'PATCH', body: changes });

export const listInvitations = ({ q, cursor } = {}) => admin(`invitations/${query({ q, cursor })}`);
export const createInvitation = (body) => admin('invitations/', { method: 'POST', body });
export const revokeInvitation = (id) => admin(`invitations/${id}/`, { method: 'DELETE' });

export const listUsers = ({ q, eligibilityState, cursor } = {}) =>
  admin(`users/${query({ q, eligibility_state: eligibilityState, cursor })}`);
export const updateUser = (id, changes) => admin(`users/${id}/`, { method: 'PATCH', body: changes });

export const listAuditLog = ({ action, resourceType, resourceId, cursor } = {}) =>
  admin(`audit-log/${query({ action, resource_type: resourceType, resource_id: resourceId, cursor })}`);
