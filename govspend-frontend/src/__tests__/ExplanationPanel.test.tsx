import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ExplanationPanel from '../components/auditor/ExplanationPanel/ExplanationPanel';
import { MOCK_EXPLANATION } from '../services/api/mockData';

describe('ExplanationPanel Component', () => {
  it('renders summary and grounding score', () => {
    render(<ExplanationPanel explanation={MOCK_EXPLANATION} />);

    expect(screen.getByText(/AI RAG Explanation & Legal Grounding/i)).toBeInTheDocument();
    expect(screen.getByText(/98.5% Grounded/i)).toBeInTheDocument();
    expect(screen.getByText(/High Risk procurement flagged/i)).toBeInTheDocument();
  });

  it('renders all explanation points and detectors', () => {
    render(<ExplanationPanel explanation={MOCK_EXPLANATION} />);

    expect(screen.getByText(/Price Deviation Detector/i)).toBeInTheDocument();
    expect(screen.getByText(/Vendor Network Risk Detector/i)).toBeInTheDocument();
    expect(screen.getByText(/Contract Splitting Detector/i)).toBeInTheDocument();
  });

  it('copies explanation to clipboard on click', () => {
    render(<ExplanationPanel explanation={MOCK_EXPLANATION} />);

    const copyBtn = screen.getByRole('button', { name: /Copy Rationale/i });
    expect(copyBtn).toBeInTheDocument();
    fireEvent.click(copyBtn);
    expect(navigator.clipboard.writeText).toHaveBeenCalled();
  });
});
