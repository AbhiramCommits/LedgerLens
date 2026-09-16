import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  categorizeTransactions,
  createAccount,
  uploadCsv,
  type ImportResponse,
} from '../api/client';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Skeleton } from '../components/Skeleton';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Select } from '../components/ui/Select';
import { analyticsKeys, useAccounts } from '../hooks/useAnalytics';
import { errorMessage } from '../lib/errors';

type UploadState =
  | { phase: 'idle' }
  | { phase: 'uploading'; percent: number }
  | { phase: 'done'; result: ImportResponse }
  | { phase: 'error'; message: string };

export function ImportPage() {
  const accounts = useAccounts();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [accountId, setAccountId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [upload, setUpload] = useState<UploadState>({ phase: 'idle' });
  const [newAccountName, setNewAccountName] = useState('');

  const createAccountMutation = useMutation({
    mutationFn: (name: string) => createAccount({ name, currency: 'USD' }),
    onSuccess: (account) => {
      void queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setAccountId(account.id);
      setNewAccountName('');
    },
  });

  const categorizeMutation = useMutation({
    mutationFn: categorizeTransactions,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: analyticsKeys.all });
      void queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });

  const selectedAccount =
    accounts.data?.find((account) => account.id === accountId) ?? accounts.data?.[0] ?? null;

  function handleFile(next: File | null) {
    if (!next) return;
    setFile(next);
    setUpload({ phase: 'idle' });
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) handleFile(dropped);
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!file || !selectedAccount) return;
    setUpload({ phase: 'uploading', percent: 0 });
    try {
      const result = await uploadCsv(selectedAccount.id, file, (percent) =>
        setUpload({ phase: 'uploading', percent }),
      );
      setUpload({ phase: 'done', result });
      void queryClient.invalidateQueries({ queryKey: ['transactions'] });
      void queryClient.invalidateQueries({ queryKey: analyticsKeys.all });
    } catch (error) {
      setUpload({ phase: 'error', message: errorMessage(error) });
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-100">Import transactions</h1>

      <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:p-5">
        <h2 className="text-base font-semibold text-slate-100">Account</h2>
        {accounts.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : accounts.isError ? (
          <ErrorState
            message={errorMessage(accounts.error)}
            onRetry={() => void accounts.refetch()}
          />
        ) : accounts.data && accounts.data.length > 0 ? (
          <Select
            label="Import into account"
            value={selectedAccount?.id ?? ''}
            options={accounts.data.map((account) => ({
              value: account.id,
              label: `${account.name} (${account.currency})`,
            }))}
            onChange={(event) => setAccountId(event.target.value)}
          />
        ) : (
          <p className="text-sm text-slate-400">
            No accounts yet — create one below before importing.
          </p>
        )}

        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const name = newAccountName.trim();
            if (name) createAccountMutation.mutate(name);
          }}
        >
          <Input
            label="New account name"
            value={newAccountName}
            onChange={(event) => setNewAccountName(event.target.value)}
            placeholder="e.g. Chase Checking"
            className="min-w-48 flex-1"
          />
          <Button
            type="submit"
            variant="secondary"
            disabled={!newAccountName.trim() || createAccountMutation.isPending}
          >
            {createAccountMutation.isPending ? 'Creating…' : 'Create account'}
          </Button>
        </form>
        {createAccountMutation.isError && (
          <p role="alert" className="text-sm text-red-400">
            {errorMessage(createAccountMutation.error)}
          </p>
        )}
      </section>

      <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-4 sm:p-5">
        <h2 className="text-base font-semibold text-slate-100">CSV file</h2>
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
            dragging ? 'border-indigo-500 bg-indigo-500/10' : 'border-slate-700 bg-slate-900/50'
          }`}
        >
          <label
            htmlFor="csv-file"
            className="cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Choose CSV file
          </label>
          <input
            ref={fileInputRef}
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            onChange={(event) => handleFile(event.target.files?.[0] ?? null)}
          />
          <p className="text-sm text-slate-400">or drag and drop a CSV here</p>
          {file && (
            <p className="text-sm text-slate-300">
              {file.name} · {(file.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>

        <form onSubmit={handleUpload}>
          <Button
            type="submit"
            disabled={!file || !selectedAccount || upload.phase === 'uploading'}
          >
            Upload
          </Button>
        </form>

        {upload.phase === 'uploading' && (
          <div>
            <div
              role="progressbar"
              aria-valuenow={upload.percent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Upload progress"
              className="h-2 w-full overflow-hidden rounded-full bg-slate-800"
            >
              <div
                className="h-full bg-indigo-500 transition-all"
                style={{ width: `${upload.percent}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-slate-400">Uploading… {upload.percent}%</p>
          </div>
        )}

        {upload.phase === 'error' && <ErrorState message={upload.message} />}

        {upload.phase === 'done' && (
          <ImportResult
            result={upload.result}
            categorizing={categorizeMutation.isPending}
            onCategorize={() => categorizeMutation.mutate()}
          />
        )}

        {categorizeMutation.isSuccess && <CategorizeSummary data={categorizeMutation.data} />}
        {categorizeMutation.isError && (
          <ErrorState message={errorMessage(categorizeMutation.error)} />
        )}
      </section>
    </div>
  );
}

function ImportResult({
  result,
  categorizing,
  onCategorize,
}: {
  result: ImportResponse;
  categorizing: boolean;
  onCategorize: () => void;
}) {
  return (
    <section
      aria-live="polite"
      className="space-y-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4"
    >
      <h3 className="text-sm font-semibold text-slate-100">Import complete</h3>
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-md bg-emerald-500/10 p-3 text-center">
          <p className="text-xl font-bold text-emerald-300">{result.inserted}</p>
          <p className="text-xs text-slate-400">inserted</p>
        </div>
        <div className="rounded-md bg-amber-500/10 p-3 text-center">
          <p className="text-xl font-bold text-amber-300">{result.skipped}</p>
          <p className="text-xs text-slate-400">skipped</p>
        </div>
        <div className="rounded-md bg-red-500/10 p-3 text-center">
          <p className="text-xl font-bold text-red-300">{result.errors.length}</p>
          <p className="text-xs text-slate-400">errors</p>
        </div>
      </div>
      {result.errors.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th scope="col" className="px-3 py-2">
                  Row
                </th>
                <th scope="col" className="px-3 py-2">
                  Reason
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {result.errors.map((rowError) => (
                <tr key={rowError.row_number}>
                  <td className="px-3 py-2 text-slate-300">{rowError.row_number}</td>
                  <td className="px-3 py-2 text-red-300">{rowError.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Button onClick={onCategorize} disabled={categorizing}>
        {categorizing ? 'Categorizing…' : 'Categorize now'}
      </Button>
    </section>
  );
}

function CategorizeSummary({ data }: { data: Awaited<ReturnType<typeof categorizeTransactions>> }) {
  const { categorized, by_source: bySource, fallback_reasons: fallbackReasons } = data;
  if (categorized === 0) {
    return (
      <EmptyState
        title="Nothing to categorize"
        description="All imported transactions already have a category."
      />
    );
  }
  return (
    <section
      aria-live="polite"
      className="space-y-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4"
    >
      <h3 className="text-sm font-semibold text-slate-100">
        Categorized {categorized} transactions
      </h3>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-300">
        <li>LLM: {bySource.llm ?? 0}</li>
        <li>Rules: {bySource.rule ?? 0}</li>
        <li>Your overrides: {bySource.user ?? 0}</li>
        <li>Fallback: {bySource.fallback ?? 0}</li>
      </ul>
      {fallbackReasons.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Fallback notes
          </p>
          {fallbackReasons.map((reason) => (
            <p key={reason} className="text-xs text-amber-300/90">
              {reason}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
