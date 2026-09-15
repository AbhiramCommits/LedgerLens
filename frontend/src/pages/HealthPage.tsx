import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from '../api/client';

export default function HealthPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 5000,
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-lg">
        <h1 className="text-2xl font-semibold">LedgerLens</h1>
        <p className="mt-1 text-sm text-slate-400">API health</p>
        {isLoading && <p className="mt-4 text-slate-300">Checking…</p>}
        {isError && <p className="mt-4 text-red-400">Unreachable: {String(error)}</p>}
        {data && (
          <div className="mt-4 space-y-1">
            <p>
              status: <span className="font-medium text-emerald-400">{data.status}</span>
            </p>
            <p>
              version: <span className="font-medium text-emerald-400">{data.version}</span>
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
