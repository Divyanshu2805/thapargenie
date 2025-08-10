import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/auth/AuthContext', () => ({ useAuth: () => ({ user: null }) }));
vi.mock('@/lib/api/chat', () => ({ chatKeys: {}, createConversation: vi.fn(), getAppConfig: vi.fn() }));

import { ImportantNotice } from './ChatHome';

function renderCard(notice) {
  return render(
    <MemoryRouter>
      <ImportantNotice notice={notice} />
    </MemoryRouter>,
  );
}

describe('ImportantNotice', () => {
  beforeEach(() => window.localStorage.clear());

  it('links to the notice and hides once dismissed on this device', () => {
    const { unmount } = renderCard({ id: 'n1', title: 'Exams moved to 3 October' });
    expect(screen.getByText('Exams moved to 3 October')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Read/ })).toHaveAttribute('href', '/notices#notice-n1');

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss this notice' }));
    expect(screen.queryByText('Exams moved to 3 October')).not.toBeInTheDocument();
    unmount();

    renderCard({ id: 'n1', title: 'Exams moved to 3 October' });
    expect(screen.queryByText('Exams moved to 3 October')).not.toBeInTheDocument();
    // A newer important notice shows again.
    renderCard({ id: 'n2', title: 'Hostel fee deadline' });
    expect(screen.getByText('Hostel fee deadline')).toBeInTheDocument();
  });

  it('renders nothing without a notice', () => {
    const { container } = renderCard(null);
    expect(container).toBeEmptyDOMElement();
  });
});
