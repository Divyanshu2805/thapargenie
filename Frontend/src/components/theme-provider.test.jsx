import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from './theme-provider';

function Probe() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  return (
    <>
      <p>
        {theme}/{resolvedTheme}
      </p>
      <button type="button" onClick={() => setTheme('dark')}>
        dark
      </button>
      <button type="button" onClick={() => setTheme('neon')}>
        invalid
      </button>
    </>
  );
}

describe('ThemeProvider', () => {
  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('applies and remembers an explicit choice', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    act(() => screen.getByRole('button', { name: 'dark' }).click());

    expect(screen.getByText('dark/dark')).toBeInTheDocument();
    expect(document.documentElement).toHaveClass('dark');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('ignores unknown themes and falls back to the stored or system value', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    act(() => screen.getByRole('button', { name: 'invalid' }).click());

    expect(screen.getByText('light/light')).toBeInTheDocument();
    expect(document.documentElement).not.toHaveClass('dark');
  });
});
