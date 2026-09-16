import type { Category } from '../api/client';

export const CATEGORY_OPTIONS: { value: Category; label: string }[] = [
  { value: 'groceries', label: 'Groceries' },
  { value: 'dining', label: 'Dining' },
  { value: 'transport', label: 'Transport' },
  { value: 'housing', label: 'Housing' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'entertainment', label: 'Entertainment' },
  { value: 'shopping', label: 'Shopping' },
  { value: 'travel', label: 'Travel' },
  { value: 'income', label: 'Income' },
  { value: 'fees', label: 'Fees' },
  { value: 'transfers', label: 'Transfers' },
  { value: 'other', label: 'Other' },
];

export const CATEGORY_COLORS: Record<Category, string> = {
  groceries: '#10b981',
  dining: '#f59e0b',
  transport: '#3b82f6',
  housing: '#8b5cf6',
  utilities: '#06b6d4',
  healthcare: '#ef4444',
  entertainment: '#ec4899',
  shopping: '#f97316',
  travel: '#14b8a6',
  income: '#22c55e',
  fees: '#64748b',
  transfers: '#a855f7',
  other: '#94a3b8',
};

export function categoryLabel(category: string): string {
  return CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}
