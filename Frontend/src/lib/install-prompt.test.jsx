import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { isIosSafari, listenForInstallPrompt, useInstallApp } from './install-prompt';

describe('isIosSafari', () => {
  it('recognises Safari on iPhone and iPad, not other iOS browsers or Android', () => {
    const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1';
    expect(isIosSafari({ userAgent: iphone, platform: 'iPhone', maxTouchPoints: 5 })).toBe(true);
    expect(isIosSafari({ userAgent: 'Mozilla/5.0 (Macintosh) Safari/605', platform: 'MacIntel', maxTouchPoints: 5 })).toBe(true);
    expect(isIosSafari({ userAgent: `${iphone} CriOS/120`, platform: 'iPhone', maxTouchPoints: 5 })).toBe(false);
    expect(isIosSafari({ userAgent: 'Mozilla/5.0 (Linux; Android 14) Chrome/120', platform: 'Linux', maxTouchPoints: 5 })).toBe(false);
    expect(isIosSafari({ userAgent: 'Mozilla/5.0 (Macintosh) Safari/605', platform: 'MacIntel', maxTouchPoints: 0 })).toBe(false);
  });
});

describe('useInstallApp', () => {
  it('offers the browser prompt once it fires, and hides after installing', async () => {
    const target = new EventTarget();
    listenForInstallPrompt(target);
    const { result } = renderHook(() => useInstallApp());
    expect(result.current.mode).toBeNull();

    const event = new Event('beforeinstallprompt', { cancelable: true });
    event.prompt = vi.fn().mockResolvedValue(undefined);
    act(() => target.dispatchEvent(event));
    expect(event.defaultPrevented).toBe(true);
    expect(result.current.mode).toBe('prompt');

    await act(() => result.current.install());
    expect(event.prompt).toHaveBeenCalled();
    act(() => target.dispatchEvent(new Event('appinstalled')));
    expect(result.current.mode).toBeNull();
  });
});
