import type { components, paths } from './schema.d';
import { getToken } from './auth';

export type ApiPaths = paths;
export type ApiSchemas = components['schemas'];
export type Transaction = components['schemas']['TransactionRead'];
export type Account = components['schemas']['AccountRead'];
export type Category = components['schemas']['Category'];
export type CategorySource = components['schemas']['CategorySource'];
export type ImportResponse = components['schemas']['ImportResponse'];
export type RowError = components['schemas']['RowError'];
export type CategorizeResponse = components['schemas']['CategorizeResponse'];
export type ByCategoryResponse = components['schemas']['ByCategoryResponse'];
export type BySourceResponse = components['schemas']['BySourceResponse'];
export type MonthlyTrendResponse = components['schemas']['MonthlyTrendResponse'];
export type MonthTotal = components['schemas']['MonthTotal'];
export type TransactionPage = components['schemas']['TransactionPage'];
export type TokenResponse = components['schemas']['TokenResponse'];

export type TransactionListQuery = paths['/api/transactions']['get']['parameters']['query'];

function describeDetail(detail: unknown): string {
  if (detail && typeof detail === 'object' && 'detail' in detail) {
    const inner = (detail as { detail: unknown }).detail;
    if (typeof inner === 'string') return inner;
    if (Array.isArray(inner) && inner.length > 0) {
      const first = inner[0] as { msg?: unknown } | null;
      if (first && typeof first === 'object' && typeof first.msg === 'string') {
        return first.msg;
      }
    }
  }
  return '';
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    const detailMessage = describeDetail(detail);
    super(
      detailMessage ? `Request failed (${status}): ${detailMessage}` : `Request failed (${status})`,
    );
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      // Non-JSON error body; keep detail null.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function loginRequest(body: components['schemas']['LoginRequest']) {
  return request<components['schemas']['TokenResponse']>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function registerRequest(body: components['schemas']['RegisterRequest']) {
  return request<components['schemas']['TokenResponse']>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function listAccounts() {
  return request<components['schemas']['AccountRead'][]>('/api/accounts');
}

export function createAccount(body: components['schemas']['AccountCreate']) {
  return request<components['schemas']['AccountRead']>('/api/accounts', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function listTransactions(query: TransactionListQuery) {
  const params = new URLSearchParams();
  if (query?.page !== undefined) params.set('page', String(query.page));
  if (query?.page_size !== undefined) params.set('page_size', String(query.page_size));
  if (query?.sort_by) params.set('sort_by', query.sort_by);
  if (query?.sort_order) params.set('sort_order', query.sort_order);
  if (query?.category) params.set('category', query.category);
  if (query?.max_confidence !== undefined && query.max_confidence !== null) {
    params.set('max_confidence', String(query.max_confidence));
  }
  const qs = params.toString();
  return request<components['schemas']['TransactionPage']>(
    `/api/transactions${qs ? `?${qs}` : ''}`,
  );
}

export function categorizeTransactions() {
  return request<components['schemas']['CategorizeResponse']>('/api/transactions/categorize', {
    method: 'POST',
  });
}

export function patchTransactionCategory(
  transactionId: string,
  body: components['schemas']['TransactionCategoryUpdate'],
) {
  return request<components['schemas']['TransactionRead']>(
    `/api/transactions/${encodeURIComponent(transactionId)}`,
    { method: 'PATCH', body: JSON.stringify(body) },
  );
}

export function byCategory(month: string) {
  return request<components['schemas']['ByCategoryResponse']>(
    `/api/analytics/by-category?month=${encodeURIComponent(month)}`,
  );
}

export function bySource(month: string) {
  return request<components['schemas']['BySourceResponse']>(
    `/api/analytics/by-source?month=${encodeURIComponent(month)}`,
  );
}

export function monthlyTrend(months: number) {
  return request<components['schemas']['MonthlyTrendResponse']>(
    `/api/analytics/monthly-trend?months=${months}`,
  );
}

export function uploadCsv(
  accountId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<components['schemas']['ImportResponse']> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/imports');
    const token = getToken();
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // Non-JSON response body.
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as components['schemas']['ImportResponse']);
      } else {
        reject(new ApiError(xhr.status, body));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, { detail: 'Network error during upload' }));
    const form = new FormData();
    form.append('account_id', accountId);
    form.append('file', file);
    xhr.send(form);
  });
}
