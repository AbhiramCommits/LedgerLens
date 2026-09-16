import type { ReactNode } from 'react';
import { errorMessage } from '../../lib/errors';
import { ErrorState } from '../ErrorState';
import { Skeleton } from '../Skeleton';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  children: ReactNode;
}

export function ChartCard({ title, subtitle, loading, error, onRetry, children }: ChartCardProps) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900 p-4 sm:p-5">
      <h2 className="text-base font-semibold text-slate-100">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-4">
        {loading ? (
          <Skeleton className="h-64 w-full" />
        ) : error ? (
          <ErrorState message={errorMessage(error)} onRetry={onRetry} />
        ) : (
          children
        )}
      </div>
    </section>
  );
}
