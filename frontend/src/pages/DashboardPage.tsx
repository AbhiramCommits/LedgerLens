import { useState, type ReactNode } from 'react';
import { ChartCard } from '../components/charts/ChartCard';
import { CategoryDonutCard } from '../components/charts/CategoryDonutCard';
import { TrendLineChart } from '../components/charts/TrendLineChart';
import { MonthPicker } from '../components/MonthPicker';
import { Skeleton } from '../components/Skeleton';
import { useByCategory, useBySource, useMonthlyTrend } from '../hooks/useAnalytics';
import { categoryLabel } from '../lib/categories';
import { errorMessage } from '../lib/errors';
import {
  currentMonthKey,
  formatCurrency,
  formatMonthKey,
  formatPercent,
  toNumber,
} from '../lib/format';

const SOURCE_ENTRIES = [
  { key: 'llm', label: 'LLM', color: '#8b5cf6' },
  { key: 'rule', label: 'Rules', color: '#3b82f6' },
  { key: 'user', label: 'You', color: '#10b981' },
] as const;

interface StatTileProps {
  label: string;
  loading: boolean;
  error: unknown;
  children: ReactNode;
}

function StatTile({ label, loading, error, children }: StatTileProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-2">
        {loading ? (
          <Skeleton className="h-7 w-24" />
        ) : error ? (
          <p className="text-sm text-red-400">{errorMessage(error)}</p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

interface SourceShareProps {
  sources: Record<string, number>;
  total: number;
}

function SourceShare({ sources, total }: SourceShareProps) {
  if (total === 0) {
    return <p className="text-sm text-slate-300">Nothing categorized yet</p>;
  }
  const entries = SOURCE_ENTRIES.map((entry) => ({
    ...entry,
    value: sources[entry.key] ?? 0,
  }));
  const description = entries
    .map((entry) => `${entry.label} ${formatPercent(total ? entry.value / total : 0)}`)
    .join(', ');
  return (
    <div>
      <div
        role="img"
        aria-label={`Categorization source share: ${description}`}
        className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-800"
      >
        {entries.map((entry) =>
          entry.value > 0 ? (
            <div
              key={entry.key}
              className="h-full"
              style={{ width: `${(entry.value / total) * 100}%`, backgroundColor: entry.color }}
            />
          ) : null,
        )}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {entries.map((entry) => (
          <li key={entry.key} className="flex items-center gap-1.5 text-xs text-slate-400">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: entry.color }}
              aria-hidden="true"
            />
            {entry.label} {formatPercent(total ? entry.value / total : 0)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function DashboardPage() {
  const [month, setMonth] = useState(currentMonthKey);
  const byCategory = useByCategory(month);
  const bySource = useBySource(month);
  const trend = useMonthlyTrend();

  const spending = (byCategory.data?.totals ?? [])
    .filter((entry) => entry.category !== 'income')
    .map((entry) => ({ category: entry.category, total: -toNumber(entry.total) }))
    .filter((entry) => entry.total > 0)
    .sort((a, b) => b.total - a.total);

  const totalSpend = spending.reduce((sum, entry) => sum + entry.total, 0);
  const transactionCount = (byCategory.data?.totals ?? []).reduce(
    (sum, entry) => sum + entry.count,
    0,
  );
  const largest = spending[0] ?? null;

  const trendPoints = (trend.data?.months ?? []).map((entry) => ({
    month: entry.month,
    spend: Math.max(0, -toNumber(entry.expenses)),
    income: Math.max(0, toNumber(entry.income)),
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <MonthPicker value={month} onChange={setMonth} />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Total spend" loading={byCategory.isLoading} error={byCategory.error}>
          <p className="text-2xl font-bold text-slate-100">{formatCurrency(totalSpend)}</p>
          <p className="mt-0.5 text-xs text-slate-500">{formatMonthKey(month)}</p>
        </StatTile>
        <StatTile label="Transactions" loading={byCategory.isLoading} error={byCategory.error}>
          <p className="text-2xl font-bold text-slate-100">{transactionCount}</p>
          <p className="mt-0.5 text-xs text-slate-500">{formatMonthKey(month)}</p>
        </StatTile>
        <StatTile label="Largest category" loading={byCategory.isLoading} error={byCategory.error}>
          {largest ? (
            <>
              <p className="text-2xl font-bold text-slate-100">{categoryLabel(largest.category)}</p>
              <p className="mt-0.5 text-xs text-slate-500">{formatCurrency(largest.total)}</p>
            </>
          ) : (
            <p className="text-sm text-slate-300">No spending yet</p>
          )}
        </StatTile>
        <StatTile label="Categorized by" loading={bySource.isLoading} error={bySource.error}>
          <SourceShare
            sources={bySource.data?.sources ?? {}}
            total={bySource.data?.total_categorized ?? 0}
          />
        </StatTile>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Spend by category"
          subtitle={formatMonthKey(month)}
          loading={byCategory.isLoading}
          error={byCategory.error}
          onRetry={() => void byCategory.refetch()}
        >
          <CategoryDonutCard data={spending} />
        </ChartCard>
        <ChartCard
          title="6-month spend trend"
          loading={trend.isLoading}
          error={trend.error}
          onRetry={() => void trend.refetch()}
        >
          <TrendLineChart data={trendPoints} />
        </ChartCard>
      </div>
    </div>
  );
}
