import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const reporting = vi.hoisted(() => ({ reportError: vi.fn(), reloadForNewVersion: vi.fn(() => false) }));
vi.mock('@/lib/error-reporting', async (importOriginal) => ({ ...(await importOriginal()), ...reporting }));

import { ErrorBoundary } from './error-boundary';

function Broken() {
  throw new Error('render failed');
}

describe('ErrorBoundary', () => {
  it('shows a recoverable screen and reports the error', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
    expect(reporting.reportError).toHaveBeenCalledWith(expect.objectContaining({ message: 'render failed' }), 'render');
  });

  it('explains an update instead when a chunk failed to load', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    function Stale() {
      throw new TypeError('Failed to fetch dynamically imported module: /assets/x.js');
    }
    render(
      <ErrorBoundary>
        <Stale />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('ThaparGenie was updated');
    expect(reporting.reloadForNewVersion).toHaveBeenCalled();
  });
});
