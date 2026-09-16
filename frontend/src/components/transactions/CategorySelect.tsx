import { useId } from 'react';
import type { Category, Transaction } from '../../api/client';
import { CATEGORY_OPTIONS } from '../../lib/categories';

interface CategorySelectProps {
  transaction: Transaction;
  pending: boolean;
  onChange: (category: Category) => void;
}

export function CategorySelect({ transaction, pending, onChange }: CategorySelectProps) {
  const id = useId();
  return (
    <>
      <label htmlFor={id} className="sr-only">
        Category for {transaction.merchant_raw || 'transaction'} on {transaction.posted_date}
      </label>
      <select
        id={id}
        value={transaction.category ?? ''}
        disabled={pending}
        onChange={(event) => {
          const next = event.target.value;
          if (next) {
            onChange(next as Category);
          }
        }}
        className="w-full min-w-36 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
      >
        <option value="">Uncategorized</option>
        {CATEGORY_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </>
  );
}
