import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000, // 2 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (tanstack query v5)
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
  queryCache: new QueryCache({
    onError: (error: any) => {
      // Avoid spamming error toasts for mock fallback queries
      if (error?.message && !error?.message?.includes('mock_fallback')) {
        console.warn('Query error caught:', error.message);
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error: any) => {
      toast.error(error?.message || 'Operation failed. Please try again.');
    },
  }),
});
