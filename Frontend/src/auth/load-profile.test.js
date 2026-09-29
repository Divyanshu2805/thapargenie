import { describe, expect, it, vi } from 'vitest';

import {
  isWarmingUp,
  loadProfileWithRetry,
  PROFILE_ATTEMPT_TIMEOUT_MS,
  PROFILE_MAX_ATTEMPTS,
} from './load-profile';

const timeout = () => Object.assign(new Error('slow'), { code: 'request_cancelled', timedOut: true });

function run(load, { current = () => true } = {}) {
  const onWaking = vi.fn();
  const sleep = vi.fn().mockResolvedValue();
  const result = loadProfileWithRetry({ load, isCurrent: current, onWaking, sleep });
  return { result, onWaking, sleep };
}

describe('isWarmingUp', () => {
  it('treats timeouts, lost connections and gateway errors as a server still starting', () => {
    expect(isWarmingUp({ timedOut: true })).toBe(true);
    expect(isWarmingUp({ code: 'network_error' })).toBe(true);
    for (const status of [502, 503, 504]) expect(isWarmingUp({ status })).toBe(true);
  });

  it('does not retry real answers or cancellations', () => {
    expect(isWarmingUp({ status: 401 })).toBe(false);
    expect(isWarmingUp({ status: 403 })).toBe(false);
    expect(isWarmingUp({ code: 'request_cancelled', timedOut: false })).toBe(false);
    expect(isWarmingUp(null)).toBe(false);
  });
});

describe('loadProfileWithRetry', () => {
  it('returns the profile with a long timeout and no waking message when the server is up', async () => {
    const load = vi.fn().mockResolvedValue({ onboarding_status: 'ready' });
    const { result, onWaking } = run(load);
    await expect(result).resolves.toEqual({ onboarding_status: 'ready' });
    expect(load).toHaveBeenCalledWith({ timeoutMs: PROFILE_ATTEMPT_TIMEOUT_MS });
    expect(onWaking).not.toHaveBeenCalled();
  });

  it('retries while the server wakes and reports it', async () => {
    const load = vi.fn().mockRejectedValueOnce(timeout()).mockResolvedValue({ onboarding_status: 'ready' });
    const { result, onWaking, sleep } = run(load);
    await expect(result).resolves.toEqual({ onboarding_status: 'ready' });
    expect(load).toHaveBeenCalledTimes(2);
    expect(onWaking).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledTimes(1);
  });

  it('gives up after the attempt limit with the last error', async () => {
    const load = vi.fn().mockRejectedValue(timeout());
    const { result } = run(load);
    await expect(result).rejects.toMatchObject({ timedOut: true });
    expect(load).toHaveBeenCalledTimes(PROFILE_MAX_ATTEMPTS);
  });

  it('fails at once on an answer that retrying cannot change', async () => {
    const load = vi.fn().mockRejectedValue(Object.assign(new Error('no'), { status: 401 }));
    const { result, onWaking } = run(load);
    await expect(result).rejects.toMatchObject({ status: 401 });
    expect(load).toHaveBeenCalledTimes(1);
    expect(onWaking).not.toHaveBeenCalled();
  });

  it('stops retrying once the user signed out or switched account', async () => {
    const load = vi.fn().mockRejectedValue(timeout());
    const { result } = run(load, { current: () => false });
    await expect(result).rejects.toMatchObject({ timedOut: true });
    expect(load).toHaveBeenCalledTimes(1);
  });
});
