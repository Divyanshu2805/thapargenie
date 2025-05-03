import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import Markdown, { linkCitations, plainMath, safeUrl } from './Markdown';

describe('plainMath', () => {
  it('turns small inline LaTeX into symbols and leaves prices and code alone', () => {
    expect(plainMath('PCM score $\\ge$ 80% but $< 80%$')).toBe('PCM score ≥ 80% but < 80%');
    expect(plainMath('fee is $500 and $600')).toBe('fee is $500 and $600');
    expect(plainMath('$\\frac{a}{b}$')).toBe('$\\frac{a}{b}$');
  });
});

describe('linkCitations', () => {
  it('turns [n] markers into citation links, including adjacent ones', () => {
    expect(linkCitations('Fee is ₹1 [1][2].')).toBe('Fee is ₹1 [1](cite:1)[2](cite:2).');
    expect(linkCitations('46th [1, 7] and [5,6].')).toBe('46th [1](cite:1)[7](cite:7) and [5](cite:5)[6](cite:6).');
    expect(linkCitations('as follows [1]:\n[2] starts a line')).toBe('as follows [1](cite:1):\n[2](cite:2) starts a line');
  });

  it('leaves real links, definitions, escapes and code alone', () => {
    expect(linkCitations('[3](https://thapar.edu)')).toBe('[3](https://thapar.edu)');
    expect(linkCitations('[3]: https://thapar.edu')).toBe('[3]: https://thapar.edu');
    expect(linkCitations('\\[4]')).toBe('\\[4]');
    expect(linkCitations('`arr[1]` and\n```\nx[2]\n```')).toBe('`arr[1]` and\n```\nx[2]\n```');
  });
});

describe('safeUrl', () => {
  it('allows web links and citations only', () => {
    expect(safeUrl('https://thapar.edu/fees')).toBe('https://thapar.edu/fees');
    expect(safeUrl('mailto:admissions@thapar.edu')).toBe('mailto:admissions@thapar.edu');
    expect(safeUrl('cite:2')).toBe('cite:2');
    expect(safeUrl('javascript:alert(1)')).toBe('');
    expect(safeUrl(' JavaScript:alert(1)')).toBe('');
    expect(safeUrl('data:text/html,<script>')).toBe('');
    expect(safeUrl('cite:2);alert(1')).toBe('');
    expect(safeUrl('/relative')).toBe('');
  });
});

describe('Markdown', () => {
  it('renders citations through the callback and GFM tables', () => {
    render(
      <Markdown
        content={'Fees [1].\n\n| Item | Fee |\n|---|---|\n| Tuition | ₹2L |'}
        renderCitation={(position) => <button type="button">cite {position}</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'cite 1' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Tuition' })).toBeInTheDocument();
  });

  it('drops raw HTML, unsafe links and remote images', () => {
    const { container } = render(
      <Markdown
        content={
          'Hi <img src=x onerror="alert(1)"> <script>alert(1)</script>\n\n[bad](javascript:alert(1)) [good](https://thapar.edu) ![pixel](https://evil.test/p.png)'
        }
      />,
    );
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('bad').closest('a')).toBeNull();
    const good = screen.getByRole('link', { name: 'good' });
    expect(good).toHaveAttribute('href', 'https://thapar.edu');
    expect(good).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });
});
