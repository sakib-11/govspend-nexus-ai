import { CaseTier, CaseStatus } from '../types';

export function formatCurrency(amount: number, currency: string = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  } catch {
    return dateString;
  }
}

export function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString).getTime();
    const now = Date.now();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return dateString;
  }
}

export function getTierColor(tier: CaseTier | string): 'error' | 'warning' | 'success' | 'default' {
  switch (tier) {
    case 'HIGH':
      return 'error';
    case 'BORDERLINE':
      return 'warning';
    case 'LOW':
      return 'success';
    default:
      return 'default';
  }
}

export function getStatusColor(status: CaseStatus | string): 'info' | 'warning' | 'success' | 'error' | 'default' {
  switch (status?.toUpperCase()) {
    case 'NEW':
      return 'info';
    case 'UNDER_REVIEW':
      return 'warning';
    case 'APPROVED':
      return 'success';
    case 'REJECTED':
      return 'error';
    case 'ESCALATED':
      return 'warning';
    case 'CLOSED':
      return 'default';
    default:
      return 'default';
  }
}

export function formatRiskScore(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}
