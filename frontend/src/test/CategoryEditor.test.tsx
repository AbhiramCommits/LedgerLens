import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useMemo } from 'react';
import { expect, test, vi, type MockInstance } from 'vitest';
import type { TransactionListQuery, TransactionPage, Transaction } from '../api/client';
import { CategorySelect } from '../components/transactions/CategorySelect';
import { useCategoryMutation } from '../hooks/useCategoryMutation';
import { useTransactions } from '../hooks/useAnalytics';

const TRANSACTION: Transaction = {
  id: '11111111-1111-1111-1111-111111111111',
  account_id: '22222222-2222-2222-2222-222222222222',
  posted_date: '2026-09-01',
  description: 'coffee run',
  merchant_raw: 'OBSCURE CAFE',
  amount: '-4.50',
  category: 'dining',
  category_source: 'rule',
  confidence: 0.9,
  created_at: '2026-09-01T10:00:00Z',
};

const QUERY: TransactionListQuery = { page: 1, page_size: 25 };

function seedCache(queryClient: QueryClient, transaction: Transaction): void {
  queryClient.setQueryData<TransactionPage>(['transactions', QUERY], {
    items: [transaction],
    total: 1,
    page: 1,
    page_size: 25,
  });
}

function EditorHarness({ onError }: { onError?: (message: string) => void }) {
  const query = useMemo(() => QUERY, []);
  const { data } = useTransactions(query);
  const mutation = useCategoryMutation(query, onError);

  if (!data || data.items.length === 0) return null;
  const transaction = data.items[0];

  return (
    <div>
      <p data-testid="displayed-category">{transaction.category}</p>
      <p data-testid="displayed-source">{transaction.category_source}</p>
      <p data-testid="displayed-confidence">{transaction.confidence}</p>
      <CategorySelect
        transaction={transaction}
        pending={mutation.isPending}
        onChange={(category) => mutation.mutate({ id: transaction.id, category })}
      />
    </div>
  );
}

function renderHarness(queryClient: QueryClient, onError?: (message: string) => void) {
  return render(
    <QueryClientProvider client={queryClient}>
      <EditorHarness onError={onError} />
    </QueryClientProvider>,
  );
}

interface DeferredResponse {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
}

function deferredFetch() {
  let resolve!: (response: DeferredResponse) => void;
  const promise = new Promise<DeferredResponse>((res) => {
    resolve = res;
  });
  const fetchMock = vi.fn(() => promise) as unknown as MockInstance<typeof fetch>;
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, resolve };
}

test('inline category editor optimistically updates the UI', async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  seedCache(queryClient, TRANSACTION);
  const { fetchMock, resolve } = deferredFetch();

  const user = userEvent.setup();
  renderHarness(queryClient);

  expect(screen.getByTestId('displayed-category')).toHaveTextContent('dining');

  await user.selectOptions(screen.getByLabelText(/Category for OBSCURE CAFE/), 'groceries');

  // Optimistic: the UI shows the new category before the server responds.
  await waitFor(() => {
    expect(screen.getByTestId('displayed-category')).toHaveTextContent('groceries');
  });
  expect(screen.getByTestId('displayed-source')).toHaveTextContent('user');
  expect(screen.getByTestId('displayed-confidence')).toHaveTextContent('1');

  const patchCall = fetchMock.mock.calls.find(
    ([input]) => String(input) === `/api/transactions/${TRANSACTION.id}`,
  );
  expect(patchCall).toBeDefined();
  expect(patchCall?.[1]).toEqual(expect.objectContaining({ method: 'PATCH' }));
  const body = JSON.parse((patchCall?.[1] as RequestInit).body as string);
  expect(body).toEqual({ category: 'groceries' });

  resolve({
    ok: true,
    status: 200,
    json: async () => ({
      ...TRANSACTION,
      category: 'groceries',
      category_source: 'user',
      confidence: 1,
    }),
  });

  await waitFor(() => {
    expect(screen.getByTestId('displayed-category')).toHaveTextContent('groceries');
  });
  expect(screen.queryByTestId('banner')).not.toBeInTheDocument();
});

test('inline category editor rolls back on server error', async () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  });
  seedCache(queryClient, TRANSACTION);
  const { resolve } = deferredFetch();

  const messages: string[] = [];
  const user = userEvent.setup();
  renderHarness(queryClient, (message) => messages.push(message));

  await user.selectOptions(screen.getByLabelText(/Category for OBSCURE CAFE/), 'shopping');
  await waitFor(() => {
    expect(screen.getByTestId('displayed-category')).toHaveTextContent('shopping');
  });

  resolve({ ok: false, status: 500, json: async () => ({ detail: 'server exploded' }) });

  await waitFor(() => {
    expect(screen.getByTestId('displayed-category')).toHaveTextContent('dining');
  });
  expect(screen.getByTestId('displayed-source')).toHaveTextContent('rule');
  expect(screen.getByTestId('displayed-confidence')).toHaveTextContent('0.9');
  expect(messages.some((message) => message.includes('server exploded'))).toBe(true);
});
