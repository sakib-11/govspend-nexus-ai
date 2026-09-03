import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import OfficerDashboard from '../components/officer/Dashboard/OfficerDashboard';

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

describe('OfficerDashboard Component', () => {
  it('renders officer executive portal headers and summary cards', async () => {
    render(<OfficerDashboard />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Government Officer Executive Portal/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText(/Pending Executive Reviews/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText(/Overall Compliance Rate/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText(/Managed Procurement Spend/i, {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it('renders compliance indicators and escalation alerts', async () => {
    render(<OfficerDashboard />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Statutory Compliance Metrics/i, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByText(/Mandatory Competitive Bidding/i, {}, { timeout: 3000 })).toBeInTheDocument();
  });
});
