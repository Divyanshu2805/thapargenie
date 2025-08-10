// Voice input through the browser's own speech recognition.
// Only the recognised text reaches ThaparGenie; nothing is recorded or uploaded by us.
import { useCallback, useEffect, useRef, useState } from 'react';

export const SPEECH_LANG = 'en-IN';

const MESSAGES = {
  'not-allowed': 'Allow microphone access in your browser to speak a question.',
  'service-not-allowed': 'Allow microphone access in your browser to speak a question.',
  'audio-capture': 'No microphone was found.',
  'no-speech': 'Didn’t catch that. Try again a little closer to the mic.',
  network: 'Voice input needs an internet connection.',
};

function recognizerClass() {
  if (typeof window === 'undefined') return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

/** Joins what was typed with what was said, with one space between. */
export function joinSpeech(base, spoken) {
  const words = spoken.trim();
  if (!words) return base;
  return base && !/\s$/.test(base) ? `${base} ${words}` : `${base}${words}`;
}

// Errors after which listening stops for good; others end one session and it restarts.
const FATAL = new Set(['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported']);

/**
 * `onText(text)` gets the whole box value while listening (typed text + what is being
 * said); `onError(message)` gets a readable reason when recognition fails.
 *
 * Listening continues until `stop()`: browsers end a session after a pause or about a
 * minute, so a new one starts at once, carrying on from the text so far. A long silence
 * at the start of a session (the browser's `no-speech`) ends it.
 */
export function useSpeechInput({ value, onText, onError }) {
  const Recognizer = recognizerClass();
  const [listening, setListening] = useState(false);
  const recognition = useRef(null);
  const wanted = useRef(false);
  const heard = useRef(false);
  const text = useRef(value);
  const latest = useRef({ onText, onError });
  const restart = useRef(null);
  useEffect(() => {
    latest.current = { onText, onError };
    text.current = value;
  });

  const listen = useCallback(() => {
    const recognizer = new Recognizer();
    recognizer.lang = SPEECH_LANG;
    recognizer.interimResults = true;
    recognizer.continuous = true;
    recognizer.maxAlternatives = 1;
    // Each session reports only its own words, so it builds on the box as it is now.
    const base = text.current;

    recognizer.onresult = (event) => {
      let spoken = '';
      for (let index = 0; index < event.results.length; index += 1) spoken += event.results[index][0].transcript;
      heard.current = true;
      const next = joinSpeech(base, spoken);
      text.current = next;
      latest.current.onText(next);
    };
    recognizer.onerror = (event) => {
      if (event.error === 'aborted') return;
      if (event.error === 'no-speech') {
        wanted.current = false;
        if (!heard.current) latest.current.onError?.(MESSAGES['no-speech']);
        return;
      }
      if (FATAL.has(event.error)) wanted.current = false;
      latest.current.onError?.(MESSAGES[event.error] || 'Voice input stopped unexpectedly.');
    };
    recognizer.onend = () => {
      recognition.current = null;
      if (wanted.current) {
        restart.current?.();
        return;
      }
      setListening(false);
    };

    recognition.current = recognizer;
    try {
      recognizer.start();
    } catch {
      recognition.current = null;
      wanted.current = false;
      setListening(false);
    }
  }, [Recognizer]);
  useEffect(() => {
    restart.current = listen;
  }, [listen]);

  const start = useCallback(() => {
    if (!Recognizer || recognition.current) return;
    wanted.current = true;
    heard.current = false;
    setListening(true);
    listen();
  }, [Recognizer, listen]);

  const stop = useCallback(() => {
    wanted.current = false;
    if (recognition.current) recognition.current.stop();
    else setListening(false);
  }, []);

  // Leaving the page (or the composer unmounting) ends listening.
  useEffect(
    () => () => {
      wanted.current = false;
      recognition.current?.abort();
    },
    [],
  );

  return { supported: Boolean(Recognizer), listening, start, stop };
}
