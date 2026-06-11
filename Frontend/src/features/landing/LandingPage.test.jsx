import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeProvider } from '@/components/theme-provider';

const auth = vi.hoisted(() => ({ user: null }));
vi.mock('@/auth/AuthContext', () => ({ useAuth: () => ({ initialized: true, user: auth.user }) }));

import LandingPage from './LandingPage';

function Destination({ name }) {
  const location = useLocation();
  return (
    <output data-testid="destination">
      {name} {JSON.stringify(location.state)}
    </output>
  );
}

function renderLanding() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login/" element={<Destination name="login" />} />
          <Route path="/register/" element={<Destination name="register" />} />
          <Route path="/chat/" element={<Destination name="chat" />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('LandingPage', () => {
  beforeEach(() => {
    auth.user = null;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('explains the product and invites visitors to sign up or sign in', () => {
    renderLanding();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Every answer about Thapar, straight from the source.');
    expect(screen.getAllByRole('link', { name: 'Sign in' })[0]).toHaveAttribute('href', '/login/');
    for (const section of ['idea', 'how', 'features', 'privacy', 'admins', 'faq']) {
      expect(document.getElementById(section)).not.toBeNull();
    }
  });

  it('carries a question typed in the FAQ through sign-in', async () => {
    renderLanding();
    fireEvent.change(screen.getByLabelText('Ask ThaparGenie a question'), { target: { value: '  When is the fee due?  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
    expect(await screen.findByTestId('destination', {}, { timeout: 3000 })).toHaveTextContent(
      'login {"from":"/chat/","draft":"When is the fee due?"}',
    );
  });

  it('hands the question to the chat box when already signed in', async () => {
    auth.user = { uid: 'u1' };
    renderLanding();
    fireEvent.change(screen.getByLabelText('Ask ThaparGenie a question'), { target: { value: 'Hostel fee for first-years' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
    expect(await screen.findByTestId('destination', {}, { timeout: 3000 })).toHaveTextContent('chat {"draft":"Hostel fee for first-years"}');
  });

  it('plays the sample conversation: the question is typed, then answered with its sources', () => {
    // Report every observed element as on screen, so the demo starts.
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(callback) {
          this.callback = callback;
        }
        observe(target) {
          this.callback([{ isIntersecting: true, target }]);
        }
        unobserve() {}
        disconnect() {}
      },
    );
    vi.useFakeTimers();
    renderLanding();
    const demo = document.querySelector('.landing-demo');
    expect(demo).not.toHaveTextContent('Hostel fee structure 2026–27.pdf');
    // Each step schedules the next after a render, so time moves in small steps until the sources show.
    for (let step = 0; step < 400 && !demo.textContent.includes('Page 3'); step += 1) {
      act(() => vi.advanceTimersByTime(50));
    }
    expect(demo).toHaveTextContent('What is the hostel fee for first-year girls?');
    expect(demo).toHaveTextContent('Understanding');
    expect(demo).toHaveTextContent('₹98,000');
    expect(demo).toHaveTextContent('Hostel fee structure 2026–27.pdf');
  });
});
