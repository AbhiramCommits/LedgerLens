import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  patchTransactionCategory,
  type Category,
  type TransactionListQuery,
  type TransactionPage,
} from '../api/client';
import { analyticsKeys } from './useAnalytics';
import { errorMessage } from '../lib/errors';

export function useCategoryMutation(
  query: TransactionListQuery,
  onError?: (message: string) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, category }: { id: string; category: Category }) =>
      patchTransactionCategory(id, { category }),
    onMutate: async ({ id, category }) => {
      await queryClient.cancelQueries({ queryKey: ['transactions'] });
      const previous = queryClient.getQueryData<TransactionPage>(['transactions', query]);
      if (previous) {
        queryClient.setQueryData<TransactionPage>(['transactions', query], {
          ...previous,
          items: previous.items.map((transaction) =>
            transaction.id === id
              ? { ...transaction, category, category_source: 'user', confidence: 1 }
              : transaction,
          ),
        });
      }
      return { previous };
    },
    onError: (error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['transactions', query], context.previous);
      }
      onError?.(`Could not update category: ${errorMessage(error)}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: analyticsKeys.all });
    },
  });
}
