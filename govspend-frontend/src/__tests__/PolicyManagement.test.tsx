import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import PolicyManagement from '../components/admin/PolicyManagement/PolicyManagement';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('PolicyManagement Component', () => {
  it('renders policy management header and new policy button', async () => {
    render(<PolicyManagement />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Policy Weights & Risk Scoring Configuration/i)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /New Policy Version/i })).toBeInTheDocument();
  });

  it('opens new policy creation dialog', async () => {
    render(<PolicyManagement />, { wrapper: createWrapper() });

    const newBtn = await screen.findByRole('button', { name: /New Policy Version/i });
    fireEvent.click(newBtn);

    expect(await screen.findByText(/Calibrate New Policy Weights Version/i)).toBeInTheDocument();
    expect(await screen.findByText(/Combined Weight Total/i)).toBeInTheDocument();
  });
});
