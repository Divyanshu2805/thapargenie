import { useQuery } from '@tanstack/react-query';

import { chatKeys, getAppConfig } from '@/lib/api/chat';

export function useAppConfig() {
  return useQuery({
    queryKey: chatKeys.appConfig,
    queryFn: ({ signal }) => getAppConfig({ signal }),
    staleTime: 60_000,
  });
}
