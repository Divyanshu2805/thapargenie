import { QueryClient } from '@tanstack/react-query';

import { registerUserStateReset } from '../utils/session';

// Errors a retry can't fix: the answer will be the same until something changes.
const NO_RETRY_STATUS = new Set([400, 401, 403, 404, 409, 422, 429]);

export function shouldRetry(failureCount, error) {
  if (failureCount >= 2) return false;
  if (error?.code === 'request_cancelled') return false;
  return !NO_RETRY_STATUS.has(error?.status);
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        staleTime: 30_000,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

export const queryClient = createQueryClient();

// Never show one account's cached data to the next account on this device.
registerUserStateReset(() => queryClient.clear());
