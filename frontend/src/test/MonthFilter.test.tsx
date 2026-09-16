import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { expect, test, vi } from 'vitest';
import type { ByCategoryResponse, BySourceResponse, MonthlyTrendResponse } from '../api/client';
import { DashboardPage } from '../pages/DashboardPage';
import { CATEGORY_OPTIONS } from '../lib/categories';

function totalsFor(month: string, diningTotal: string): ByCategoryResponse {
  return {
    month,
    totals: CATEGORY_OPTIONS.map(({ value }) => ({
      category: value,
      total: value === 'dining' ? diningTotal : '0',
      count: value === 'dining' ? 3 : 0,
    })),
  };
}

function sourcesFor(month: string): BySourceResponse {
  return {
    month,
    sources: { llm: 1, rule: 2, user: 0 },
    total_categorized: 3,
    uncategorized: 0,
  };
}

function trendFor(): MonthlyTrendResponse {
  return {
    months: [
      { month: '2026-04', total: '0', income: '0', expenses: '0', count: 0 },
      { month: '2026-05', total: '0', income: '0', expenses: '0', count: 0 },
      { month: '2026-06', total: '0', income: '0', expenses: '0', count: 0 },
      { month: '2026-07', total: '0', income: '0', expenses: '0', count: 0 },
      { month: '2026-08', total: '-80.00', income: '0', expenses: '-80.00', count: 3 },
      { month: '2026-09', total: '-120.50', income: '0', expenses: '-120.50', count: 3 },
    ],
  };
}

function Wrapper({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

test('month picker drives the dashboard widgets', async () => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-09-15T12:00:00Z'));

  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/analytics/by-category')) {
      const month = new URL(url, 'http://test').searchParams.get('month');
      const total = month === '2026-08' ? '-80.00' : '-120.50';
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => totalsFor(month ?? '2026-09', total),
      });
    }
    if (url.includes('/api/analytics/by-source')) {
      const month = new URL(url, 'http://test').searchParams.get('month');
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => sourcesFor(month ?? '2026-09'),
      });
    }
    if (url.includes('/api/analytics/monthly-trend')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => trendFor() });
    }
    return Promise.reject(new Error(`unexpected request: ${url}`));
  });
  vi.stubGlobal('fetch', fetchMock);

  render(
    <Wrapper>
      <DashboardPage />
    </Wrapper>,
  );

  // Default month is the current month (2026-09 given the mocked clock).
  await waitFor(() => expect(screen.getAllByText('$120.50').length).toBeGreaterThan(0));
  expect(screen.getByLabelText('Month')).toHaveValue('2026-09');

  fireEvent.change(screen.getByLabelText('Month'), { target: { value: '2026-08' } });

  await waitFor(() => {
    expect(screen.getAllByText('$80.00').length).toBeGreaterThan(0);
    expect(screen.queryByText('$120.50')).not.toBeInTheDocument();
  });
  expect(screen.getByLabelText('Month')).toHaveValue('2026-08');

  const requestedMonths = fetchMock.mock.calls
    .map(([input]) => String(input))
    .filter((url) => url.includes('/api/analytics/by-category'))
    .map((url) => new URL(url, 'http://test').searchParams.get('month'));
  expect(requestedMonths).toContain('2026-08');
});
