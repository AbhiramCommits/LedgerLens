import { useEffect, useMemo, useState } from 'react';
import { type Category, type TransactionListQuery } from '../api/client';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Pagination } from '../components/Pagination';
import { SkeletonRows } from '../components/Skeleton';
import { CategorySelect } from '../components/transactions/CategorySelect';
import { ConfidenceBadge } from '../components/transactions/ConfidenceBadge';
import { Select } from '../components/ui/Select';
import { useCategoryMutation } from '../hooks/useCategoryMutation';
import { useTransactions } from '../hooks/useAnalytics';
import { CATEGORY_OPTIONS } from '../lib/categories';
import { errorMessage } from '../lib/errors';
import { formatCurrency, formatDate, toNumber } from '../lib/format';

const PAGE_SIZE = 25;

type SortKey = 'posted_date' | 'merchant_raw' | 'amount' | 'category';
type SortOrder = 'asc' | 'desc';

const SORTABLE_COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'posted_date', label: 'Date' },
  { key: 'merchant_raw', label: 'Merchant' },
  { key: 'amount', label: 'Amount' },
  { key: 'category', label: 'Category' },
];

const CONFIDENCE_FILTERS = [
  { value: '', label: 'Any confidence' },
  { value: '0.5', label: 'Low confidence (≤ 50%)' },
  { value: '0.9', label: 'Unreviewed (≤ 90%)' },
  { value: '0', label: 'No / zero confidence' },
];

export function TransactionsPage() {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortKey>('posted_date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [confidenceFilter, setConfidenceFilter] = useState('');
  const [actionError, setActionError] = useState<string | null>(null);

  const query = useMemo<TransactionListQuery>(
    () => ({
      page,
      page_size: PAGE_SIZE,
      sort_by: sortBy,
      sort_order: sortOrder,
      category: categoryFilter ? (categoryFilter as Category) : null,
      max_confidence: confidenceFilter === '' ? null : Number(confidenceFilter),
    }),
    [page, sortBy, sortOrder, categoryFilter, confidenceFilter],
  );

  const transactions = useTransactions(query);

  const categoryMutation = useCategoryMutation(query, (message) => setActionError(message));

  useEffect(() => {
    if (categoryMutation.isSuccess) setActionError(null);
  }, [categoryMutation.isSuccess]);

  function toggleSort(key: SortKey) {
    if (sortBy === key) {
      setSortOrder((order) => (order === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortOrder('desc');
    }
    setPage(1);
  }

  const items = transactions.data?.items ?? [];
  const total = transactions.data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-100">Transactions</h1>
        <div className="flex flex-wrap items-end gap-3">
          <Select
            label="Category"
            value={categoryFilter}
            options={CATEGORY_OPTIONS}
            placeholder="All categories"
            onChange={(event) => {
              setCategoryFilter(event.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Confidence"
            value={confidenceFilter}
            options={CONFIDENCE_FILTERS}
            onChange={(event) => {
              setConfidenceFilter(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </div>

      {actionError && (
        <p role="alert" className="rounded-md bg-red-950/50 p-3 text-sm text-red-300">
          {actionError}
        </p>
      )}

      {transactions.isLoading ? (
        <SkeletonRows rows={8} />
      ) : transactions.isError ? (
        <ErrorState
          message={errorMessage(transactions.error)}
          onRetry={() => void transactions.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="No transactions"
          description="Import a CSV file or adjust the filters to see transactions here."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="bg-slate-900 text-xs uppercase tracking-wide text-slate-400">
              <tr>
                {SORTABLE_COLUMNS.map((column) => (
                  <th
                    key={column.key}
                    scope="col"
                    className="px-4 py-3"
                    aria-sort={
                      sortBy === column.key
                        ? sortOrder === 'asc'
                          ? 'ascending'
                          : 'descending'
                        : 'none'
                    }
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="inline-flex items-center gap-1 font-medium hover:text-white"
                    >
                      {column.label}
                      {sortBy === column.key && (
                        <span aria-hidden="true">{sortOrder === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </button>
                  </th>
                ))}
                <th scope="col" className="px-4 py-3">
                  Confidence
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-900/50">
              {items.map((transaction) => (
                <tr key={transaction.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3 text-slate-300">
                    {formatDate(transaction.posted_date)}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-100">
                    {transaction.merchant_raw || '—'}
                  </td>
                  <td
                    className={`px-4 py-3 font-medium ${
                      toNumber(transaction.amount) < 0 ? 'text-red-300' : 'text-emerald-300'
                    }`}
                  >
                    {formatCurrency(transaction.amount)}
                  </td>
                  <td className="px-4 py-3">
                    <CategorySelect
                      transaction={transaction}
                      pending={categoryMutation.isPending}
                      onChange={(category) =>
                        categoryMutation.mutate({ id: transaction.id, category })
                      }
                    />
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBadge transaction={transaction} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!transactions.isLoading && !transactions.isError && total > 0 && (
        <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPageChange={setPage} />
      )}
    </div>
  );
}
