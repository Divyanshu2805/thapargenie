import { describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api/admin', () => ({}));
vi.mock('@/lib/api/chat', () => ({ chatKeys: {} }));
vi.mock('@/components/recent-auth', () => ({ useRecentAuth: () => (action) => action() }));

import { cleanMeta, validateMeta } from './AddKnowledgeDialog';
import { actorLabel, describeAction } from './AuditLogPage';
import { niceMax } from './charts';
import { validityOf } from './constants';
import { changedFields } from './DocumentDetailPage';
import { faqDraft } from './FeedbackPage';
import { summarize } from './OverviewPage';
import { settingsChanges, validateSettings } from './SettingsAdminPage';
import { formatBytes, formatMs, formatPercent, formatRelative } from '@/lib/format';

describe('document metadata', () => {
  it('drops empty fields and trims text', () => {
    expect(cleanMeta({ category: 'faq', academic_year: ' 2026-27 ', department: '', is_current: false, source_url: null })).toEqual({
      category: 'faq',
      academic_year: '2026-27',
      is_current: false,
    });
  });

  it('checks the academic year and https links', () => {
    expect(validateMeta({ academic_year: '2026', source_url: 'http://thapar.edu' })).toEqual({
      academic_year: 'Use the form 2026-27.',
      source_url: 'Only https links are allowed.',
    });
    expect(validateMeta({ academic_year: '2026-27', source_url: 'https://thapar.edu' })).toEqual({});
  });

  it('sends only changed fields, with a cleared date as null', () => {
    const original = { title: 'Fees', category: 'faq', department: '', academic_year: '2025-26', effective_date: '2025-07-01', valid_until: '2026-06-30', is_current: true, source_url: '' };
    const form = { ...original, title: ' Fees 2026 ', effective_date: '', valid_until: '', is_current: false };
    expect(changedFields(original, form)).toEqual({ title: 'Fees 2026', effective_date: null, valid_until: null, is_current: false });
    expect(changedFields(original, { ...original, valid_until: '2027-06-30' })).toEqual({ valid_until: '2027-06-30' });
  });

  it('refuses a "valid until" before the effective date', () => {
    expect(validateMeta({ effective_date: '2026-08-01', valid_until: '2026-07-31' })).toEqual({
      valid_until: '“Valid until” can’t be before the effective date.',
    });
    expect(validateMeta({ effective_date: '2026-08-01', valid_until: '2026-08-01' })).toEqual({});
    expect(validateMeta({ valid_until: '2026-07-31' })).toEqual({});
  });
});

describe('document validity', () => {
  const NOW = new Date(2026, 8, 25, 15, 30);

  it('flags documents expiring within 30 days, inclusive of today', () => {
    expect(validityOf({ valid_until: '2026-09-25' }, NOW)).toEqual({ state: 'expiring', label: 'Expires 25 Sept 2026' });
    expect(validityOf({ valid_until: '2026-10-25' }, NOW)).toEqual({ state: 'expiring', label: 'Expires 25 Oct 2026' });
    expect(validityOf({ valid_until: '2026-10-26' }, NOW)).toBeNull();
  });

  it('flags documents past their date', () => {
    expect(validityOf({ valid_until: '2026-09-24' }, NOW)).toEqual({ state: 'expired', label: 'Expired 24 Sept 2026' });
  });

  it('ignores documents without a date', () => {
    expect(validityOf({ valid_until: null }, NOW)).toBeNull();
    expect(validityOf({}, NOW)).toBeNull();
  });
});

describe('admin settings', () => {
  const saved = {
    daily_question_limit: 30,
    global_daily_llm_calls: 5000,
    rerank_enabled: false,
    cache_enabled: true,
    contextualize_default: true,
    auto_title_enabled: true,
    maintenance_mode: false,
    maintenance_message: '',
    banner_text: '',
    starter_questions: [{ category: 'Fees', text: 'Fee?' }],
    require_approval: true,
    updated_at: '2026-09-25T10:00:00Z',
  };

  it('sends the approval switch only when it changes', () => {
    expect(settingsChanges(saved, { ...saved, require_approval: false })).toEqual({ require_approval: false });
  });

  it('diffs nested starter questions and ignores read-only fields', () => {
    const form = { ...saved, starter_questions: [{ category: 'Fees', text: 'Fee 2026?' }], updated_at: 'x' };
    expect(settingsChanges(saved, form)).toEqual({ starter_questions: [{ category: 'Fees', text: 'Fee 2026?' }] });
    expect(settingsChanges(saved, structuredClone(saved))).toEqual({});
  });

  it('requires a maintenance message, sane limits and complete starters', () => {
    const errors = validateSettings({
      ...saved,
      daily_question_limit: 0,
      global_daily_llm_calls: 50,
      maintenance_mode: true,
      starter_questions: [{ category: '', text: 'x' }],
    });
    expect(Object.keys(errors).sort()).toEqual([
      'daily_question_limit',
      'global_daily_llm_calls',
      'maintenance_message',
      'starter_questions',
    ]);
    expect(validateSettings(saved)).toEqual({});
  });
});

describe('overview summary', () => {
  it('counts cached answers as answered and ignores small talk', () => {
    const result = summarize({
      answer_types: { answered: 6, cached: 2, no_answer: 2, smalltalk: 5 },
      feedback: { up: 3, down: 1 },
    });
    expect(result).toEqual({ answeredRate: 0.8, satisfaction: 0.75, ratings: 4 });
  });

  it('returns null rates with no data', () => {
    expect(summarize({ answer_types: {}, feedback: { up: 0, down: 0 } })).toEqual({ answeredRate: null, satisfaction: null, ratings: 0 });
  });
});

describe('helpers', () => {
  it('prefills an FAQ from a student question', () => {
    expect(faqDraft('  Hostel fee? ')).toEqual({ tab: 'text', title: 'Hostel fee?', text: 'Q: Hostel fee?\nA: ', meta: { category: 'faq' } });
  });

  it('labels audit actors, including the system and deleted accounts', () => {
    expect(actorLabel({ actor_email: 'a@thapar.edu', actor_kind: 'user' })).toBe('a@thapar.edu');
    expect(actorLabel({ actor_email: null, actor_kind: 'service' })).toBe('System');
    expect(actorLabel({ actor_email: null, actor_kind: 'user' })).toBe('Deleted account');
  });

  it('picks a tight, round chart axis', () => {
    expect([3, 9, 18, 21, 130, 999].map(niceMax)).toEqual([4, 10, 20, 30, 200, 1000]);
  });

  it('describes audit actions', () => {
    expect(describeAction('identity.invitation_created')).toBe('identity · invitation created');
  });

  it('formats values for tiles', () => {
    expect(formatMs(840)).toBe('840 ms');
    expect(formatMs(4800)).toBe('4.8 s');
    expect(formatPercent(0.756)).toBe('76%');
    expect(formatPercent(null)).toBe('—');
    expect(formatBytes(52_428_800)).toBe('50 MB');
    expect(formatRelative('2026-09-25T09:00:00Z', Date.parse('2026-09-25T12:00:00Z'))).toBe('3 hours ago');
  });
});
