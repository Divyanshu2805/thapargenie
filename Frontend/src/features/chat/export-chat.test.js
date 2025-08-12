import { afterEach, describe, expect, it, vi } from 'vitest';

import { chatFilename, chatToMarkdown, printChat } from './export-chat';

const NOW = new Date('2026-09-26T10:00:00Z');

describe('chatFilename', () => {
  it('makes a short, safe name with the date', () => {
    expect(chatFilename('Hostel fees: 2026–27?', NOW)).toBe('thapargenie-hostel-fees-202627-2026-09-26.md');
    expect(chatFilename('', NOW)).toBe('thapargenie-chat-2026-09-26.md');
    expect(chatFilename('!!!', NOW)).toBe('thapargenie-chat-2026-09-26.md');
  });
});

describe('chatToMarkdown', () => {
  it('lists each question and answer with the cited sources', () => {
    const markdown = chatToMarkdown({ title: 'Hostel fees' }, [
      { role: 'user', content: 'What is the hostel fee?' },
      {
        role: 'assistant',
        content: 'It is Rs 1,20,000 a year [1].',
        sources: [
          { position: 1, title: 'Fee notice', url: 'https://www.thapar.edu/fees', heading_path: 'Hostel', page_start: 2, cited: true },
          { position: 2, title: 'Stored scan', url: '', cited: true },
          { position: 3, title: 'Unused', url: 'https://www.thapar.edu/x', cited: false },
        ],
      },
      { role: 'assistant', content: '' },
    ], NOW);

    expect(markdown).toContain('# Hostel fees');
    expect(markdown).toContain('**You:** What is the hostel fee?');
    expect(markdown).toContain('It is Rs 1,20,000 a year [1].');
    expect(markdown).toContain('1. [Fee notice (Hostel, p. 2)](https://www.thapar.edu/fees)');
    expect(markdown).toContain('2. Stored scan');
    expect(markdown).not.toContain('Unused');
  });
});

describe('printChat', () => {
  afterEach(() => document.documentElement.classList.remove('dark'));

  it('prints in the light theme and restores dark afterwards', () => {
    document.documentElement.classList.add('dark');
    const print = vi.fn(() => {
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
    window.print = print;
    printChat();
    expect(print).toHaveBeenCalled();
    window.dispatchEvent(new Event('afterprint'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    delete window.print;
  });
});
