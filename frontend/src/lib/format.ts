const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
});

const monthFormatter = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' });
const shortMonthFormatter = new Intl.DateTimeFormat('en-US', { month: 'short' });
const dateFormatter = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' });

export function toNumber(value: number | string | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0;
  return typeof value === 'number' ? value : Number(value);
}

export function formatCurrency(value: number | string | null | undefined): string {
  return currencyFormatter.format(toNumber(value));
}

export function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

export function formatMonthKey(key: string): string {
  const [year, month] = key.split('-');
  if (!year || !month) return key;
  return monthFormatter.format(new Date(Number(year), Number(month) - 1, 1));
}

export function formatShortMonth(key: string): string {
  const [year, month] = key.split('-');
  if (!year || !month) return key;
  return shortMonthFormatter.format(new Date(Number(year), Number(month) - 1, 1));
}

export function currentMonthKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
