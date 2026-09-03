import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import CaseQueue from '../components/auditor/CaseQueue/CaseQueue';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('CaseQueue Component', () => {
  it('renders queue title and preset filter buttons', async () => {
    render(<CaseQueue />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Procurement Case Audit Queue/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /All Cases/i }, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /High Risk Only/i }, { timeout: 3000 })).toBeInTheDocument();
  });

  it('renders table headers and case items', async () => {
    render(<CaseQueue />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Procurement Case Audit Queue/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Case ID/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Department/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Risk Score/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /Billed Amount/i })).toBeInTheDocument();
  });
});
