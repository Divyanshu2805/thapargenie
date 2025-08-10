// Student notices. The admin calls live in `admin.js`.
import { apiRequest } from '../../utils/apiClient';

export const noticeKeys = {
  list: (category) => ['notices', category || 'all'],
  official: ['notices', 'official'],
};

export const listNotices = ({ category } = {}, { signal } = {}) =>
  apiRequest(`notices/${category ? `?category=${encodeURIComponent(category)}` : ''}`, { signal });

export const listOfficialNotices = ({ days = 30 } = {}, { signal } = {}) =>
  apiRequest(`notices/official/?days=${days}`, { signal });

export const openOfficialNotice = (documentId) => apiRequest(`notices/official/${documentId}/open/`);
