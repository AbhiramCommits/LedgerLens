import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  byCategory,
  bySource,
  listAccounts,
  listTransactions,
  monthlyTrend,
  type TransactionListQuery,
} from '../api/client';

export const analyticsKeys = {
  all: ['analytics'] as const,
  byCategory: (month: string) => ['analytics', 'by-category', month] as const,
  bySource: (month: string) => ['analytics', 'by-source', month] as const,
  trend: ['analytics', 'monthly-trend'] as const,
};

export function useByCategory(month: string) {
  return useQuery({
    queryKey: analyticsKeys.byCategory(month),
    queryFn: () => byCategory(month),
  });
}

export function useBySource(month: string) {
  return useQuery({
    queryKey: analyticsKeys.bySource(month),
    queryFn: () => bySource(month),
  });
}

export function useMonthlyTrend() {
  return useQuery({
    queryKey: analyticsKeys.trend,
    queryFn: () => monthlyTrend(6),
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
  });
}

export function useTransactions(query: TransactionListQuery) {
  return useQuery({
    queryKey: ['transactions', query],
    queryFn: () => listTransactions(query),
    placeholderData: keepPreviousData,
  });
}
