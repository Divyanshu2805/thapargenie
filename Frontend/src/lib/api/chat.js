// Student API. JSON calls go through `apiRequest`; the two
// answer endpoints are SSE streams through `streamRequest`.
import { apiBlobRequest, apiRequest } from '../../utils/apiClient';
import { API_BASE_URL } from '../../utils/constants';
import { streamRequest } from '../http';

export const chatKeys = {
  appConfig: ['app-config'],
  coverage: ['coverage'],
  conversations: (filters = {}) => ['conversations', filters],
  conversation: (id) => ['conversation', id],
  messages: (id) => ['conversation', id, 'messages'],
  siteFeedback: ['site-feedback'],
  share: (messageId) => ['share', messageId],
  shared: (token) => ['shared', token],
};

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export const getAppConfig = ({ signal } = {}) => apiRequest('app-config/', { signal });

// Topics the knowledge base covers, with document counts ("What can I ask?").
export const getCoverage = ({ signal } = {}) => apiRequest('coverage/', { signal });

export const listConversations = ({ archived, q, cursor, pageSize } = {}, { signal } = {}) =>
  apiRequest(`conversations/${query({ archived, q, cursor, page_size: pageSize })}`, { signal });

export const createConversation = (title) =>
  apiRequest('conversations/', { method: 'POST', body: title ? { title } : {} });

export const updateConversation = (id, changes) =>
  apiRequest(`conversations/${id}/`, { method: 'PATCH', body: changes });

export const deleteConversation = (id) => apiRequest(`conversations/${id}/`, { method: 'DELETE' });

export const deleteAllConversations = () => apiRequest('conversations/', { method: 'DELETE' });

export const getMessages = (id, { signal } = {}) => apiRequest(`conversations/${id}/messages/`, { signal });

export const askQuestion = (conversationId, { content, clientRequestId, editOf }, { signal } = {}) =>
  streamRequest(
    `conversations/${conversationId}/messages/`,
    { content, client_request_id: clientRequestId, ...(editOf ? { edit_of: editOf } : {}) },
    { signal },
  );

export const regenerateAnswer = (messageId, { clientRequestId }, { signal } = {}) =>
  streamRequest(`messages/${messageId}/regenerate/`, { client_request_id: clientRequestId }, { signal });

export const setFeedback = (messageId, { rating, reason, comment }) =>
  apiRequest(`messages/${messageId}/feedback/`, { method: 'PUT', body: { rating, reason, comment } });

export const clearFeedback = (messageId) => apiRequest(`messages/${messageId}/feedback/`, { method: 'DELETE' });

export const openSource = (sourceId) => apiRequest(`sources/${sourceId}/open/`);

// One AI call the first time, then served from the saved message.
export const getSuggestions = (messageId) =>
  apiRequest(`messages/${messageId}/suggestions/`, { method: 'POST', timeoutMs: 30_000 });

export const updatePreferences = (preferences) => apiRequest('me/', { method: 'PATCH', body: preferences });

/** Ends every session on every device (needs a recent sign-in). */
export const revokeAllSessions = () => apiRequest('me/revoke-sessions/', { method: 'POST' });

/** Resolves to `{blob, contentDisposition}` for a browser download. */
export const exportMyData = () => apiBlobRequest('me/export/', { timeoutMs: 60_000 });

// Share an answer: the student's 7-day public link, and the public view.
export const getShare = (messageId, { signal } = {}) => apiRequest(`messages/${messageId}/share/`, { signal });
export const createShare = (messageId) => apiRequest(`messages/${messageId}/share/`, { method: 'POST' });
export const revokeShare = (messageId) => apiRequest(`messages/${messageId}/share/`, { method: 'DELETE' });

/** Public, so no sign-in and no token: a plain fetch. Resolves to null when the link is gone. */
export async function getSharedAnswer(token, { signal } = {}) {
  const response = await fetch(new URL(`shared/${encodeURIComponent(token)}/`, API_BASE_URL), {
    headers: { Accept: 'application/json' },
    credentials: 'omit',
    signal,
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(response.status === 429 ? 'Too many requests. Try again in a minute.' : 'The link couldn’t be opened right now.');
  return response.json();
}

// Feedback on the site itself.
export const listSiteFeedback = ({ signal } = {}) => apiRequest('site-feedback/', { signal });

export const sendSiteFeedback = ({ kind, rating, message, page, contactOk }) =>
  apiRequest('site-feedback/', {
    method: 'POST',
    body: { kind, rating: rating ?? null, message, page, contact_ok: contactOk },
  });
