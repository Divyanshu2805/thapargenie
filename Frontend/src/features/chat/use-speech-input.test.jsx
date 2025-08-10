import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock('sonner', () => ({ toast }));

import Composer from './Composer';
import { SPEECH_LANG, joinSpeech } from './use-speech-input';

class FakeRecognition {
  static last = null;
  static sessions = 0;
  constructor() {
    FakeRecognition.last = this;
    FakeRecognition.sessions += 1;
    this.started = false;
  }
  start() {
    this.started = true;
  }
  stop() {
    this.onend?.();
  }
  abort() {
    this.onend?.();
  }
  /** Simulates the browser reporting results: [[text, isFinal], …]. */
  emit(parts) {
    const results = parts.map(([text, isFinal]) => Object.assign([{ transcript: text }], { isFinal }));
    this.onresult?.({ results });
  }
}

function Harness({ initial = '' }) {
  const [value, setValue] = useState(initial);
  return <Composer value={value} onChange={setValue} onSubmit={vi.fn()} />;
}

describe('joinSpeech', () => {
  it('adds a space between typed and spoken words only when needed', () => {
    expect(joinSpeech('', ' hostel fees ')).toBe('hostel fees');
    expect(joinSpeech('What are the', 'hostel fees')).toBe('What are the hostel fees');
    expect(joinSpeech('What are the ', 'hostel fees')).toBe('What are the hostel fees');
    expect(joinSpeech('Typed', '   ')).toBe('Typed');
  });
});

describe('voice input in the composer', () => {
  beforeEach(() => {
    window.webkitSpeechRecognition = FakeRecognition;
    toast.error.mockClear();
  });
  afterEach(() => {
    delete window.webkitSpeechRecognition;
    FakeRecognition.last = null;
    FakeRecognition.sessions = 0;
  });

  it('shows no mic where the browser has no speech recognition', () => {
    delete window.webkitSpeechRecognition;
    render(<Harness />);
    expect(screen.queryByRole('button', { name: 'Speak your question' })).not.toBeInTheDocument();
  });

  it('writes what is said after what was typed, in Indian English, without sending', () => {
    render(<Harness initial="Tell me" />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak your question' }));
    const recognizer = FakeRecognition.last;
    expect(recognizer.started).toBe(true);
    expect(recognizer.lang).toBe(SPEECH_LANG);
    expect(recognizer.continuous).toBe(true);
    expect(screen.getByRole('button', { name: 'Stop listening' })).toHaveAttribute('aria-pressed', 'true');

    act(() => recognizer.emit([['the hostel', false]]));
    expect(screen.getByLabelText('Ask a question about TIET')).toHaveValue('Tell me the hostel');
    act(() => recognizer.emit([['the hostel fees', true]]));
    expect(screen.getByLabelText('Ask a question about TIET')).toHaveValue('Tell me the hostel fees');

    fireEvent.click(screen.getByRole('button', { name: 'Stop listening' }));
    expect(screen.getByRole('button', { name: 'Speak your question' })).toBeInTheDocument();
  });

  it('keeps listening after the browser ends a session, carrying on from the text so far', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak your question' }));
    act(() => FakeRecognition.last.emit([['What is the hostel fee', true]]));
    // The browser ends the session after a pause; a new one starts on its own.
    act(() => FakeRecognition.last.onend());
    expect(FakeRecognition.sessions).toBe(2);
    expect(FakeRecognition.last.started).toBe(true);
    expect(screen.getByRole('button', { name: 'Stop listening' })).toBeInTheDocument();

    act(() => FakeRecognition.last.emit([['for first years', true]]));
    expect(screen.getByLabelText('Ask a question about TIET')).toHaveValue('What is the hostel fee for first years');

    // Silence at the start of a session ends listening, without an error once words were heard.
    act(() => {
      FakeRecognition.last.onerror({ error: 'no-speech' });
      FakeRecognition.last.onend();
    });
    expect(FakeRecognition.sessions).toBe(2);
    expect(screen.getByRole('button', { name: 'Speak your question' })).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('explains a blocked microphone', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak your question' }));
    act(() => {
      FakeRecognition.last.onerror({ error: 'not-allowed' });
      FakeRecognition.last.onend();
    });
    expect(toast.error).toHaveBeenCalledWith('Allow microphone access in your browser to speak a question.');
  });
});
