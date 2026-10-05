// A free-tier API that has been idle takes 30–60 s to wake up, longer than the 10 s default
// timeout. Rather than showing "Unable to check account", wait longer for the profile and
// retry while the server looks like it is still starting.
export const PROFILE_ATTEMPT_TIMEOUT_MS = 25_000;
export const PROFILE_MAX_ATTEMPTS = 3;
const RETRY_DELAY_MS = 2_000;

const defaultSleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

// Our own timeout, no connection, or a gateway/identity 5xx. A 401/403 is a real answer.
export function isWarmingUp(error) {
  if (!error) return false;
  if (error.timedOut || error.code === 'network_error') return true;
  return [502, 503, 504].includes(error.status);
}

export async function loadProfileWithRetry({ load, isCurrent, onWaking, sleep = defaultSleep }) {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await load({ timeoutMs: PROFILE_ATTEMPT_TIMEOUT_MS });
    } catch (error) {
      if (attempt >= PROFILE_MAX_ATTEMPTS || !isWarmingUp(error) || !isCurrent()) throw error;
      onWaking();
      await sleep(RETRY_DELAY_MS);
      if (!isCurrent()) throw error;
    }
  }
}
