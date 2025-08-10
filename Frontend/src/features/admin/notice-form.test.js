import { describe, expect, it } from 'vitest';

import { emptyForm, endOfDay, formFromNotice, toPayload, validateNotice } from './notice-form';

const NOW = new Date(2026, 8, 26, 12, 0);

describe('validateNotice', () => {
  it('needs a title, an https link and future dates', () => {
    const errors = validateNotice(
      { ...emptyForm(), link_url: 'http://x.example', schedule: true, publish_date: '2026-09-26', publish_time: '11:00', expires_on: '2026-09-25' },
      NOW,
    );
    expect(Object.keys(errors).sort()).toEqual(['expires_on', 'link_url', 'publish', 'title']);
  });

  it('wants the expiry after a scheduled publish', () => {
    const form = { ...emptyForm(), title: 'Exams', schedule: true, publish_date: '2026-10-05', publish_time: '09:00', expires_on: '2026-10-01' };
    expect(validateNotice(form, NOW)).toEqual({ expires_on: 'The expiry must be after the publish time.' });
    expect(validateNotice({ ...form, expires_on: '2026-10-05' }, NOW)).toEqual({});
  });

  it('lets an expired notice be edited without touching its expiry', () => {
    const original = { title: 'Old', body: '', category: 'notices', importance: 'normal', is_pinned: false, state: 'expired', publish_at: '2026-09-01T04:00:00Z', expires_at: '2026-09-10T18:29:59Z', link_url: '', answerable: true };
    expect(validateNotice(formFromNotice(original), NOW, original)).toEqual({});
  });
});

describe('toPayload', () => {
  it('publishes now unless scheduled, with the expiry at the end of the day', () => {
    const form = { ...emptyForm(), title: '  Fee deadline ', body: ' Pay by Friday. ', important: true, expires_on: '2026-10-15' };
    expect(toPayload(form, { draft: false })).toEqual({
      title: 'Fee deadline',
      body: 'Pay by Friday.',
      category: 'notices',
      importance: 'important',
      is_pinned: false,
      is_draft: false,
      link_url: '',
      answerable: true,
      expires_at: endOfDay('2026-10-15').toISOString(),
    });
  });

  it('sends the scheduled time, and null to publish a scheduled notice now', () => {
    const scheduled = { ...emptyForm(), title: 'Exams', schedule: true, publish_date: '2026-10-05', publish_time: '09:30' };
    expect(toPayload(scheduled, { draft: true }).publish_at).toBe(new Date(2026, 9, 5, 9, 30).toISOString());

    const original = { title: 'Exams', body: '', category: 'notices', importance: 'normal', is_pinned: false, state: 'scheduled', publish_at: '2026-10-05T04:00:00Z', expires_at: null, link_url: '', answerable: true };
    const payload = toPayload({ ...formFromNotice(original), schedule: false }, { draft: false, original });
    expect(payload.publish_at).toBeNull();
    expect('expires_at' in payload).toBe(false);
  });
});
