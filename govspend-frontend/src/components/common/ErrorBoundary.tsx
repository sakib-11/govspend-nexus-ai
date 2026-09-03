import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          className="error-boundary pastel-card"
          style={{
            padding: '40px',
            textAlign: 'center',
            maxWidth: '520px',
            margin: '80px auto',
            background: '#FFFFFF',
            borderRadius: '16px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.06)',
            border: '1px solid #F0EDEA',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🛡️</div>
          <h2 style={{ color: '#2D3748', marginBottom: '8px', fontWeight: 700 }}>
            Something went wrong
          </h2>
          <p style={{ color: '#5A6B7C', marginBottom: '24px', lineHeight: 1.5 }}>
            GovSpend Nexus AI recovered safely. Please refresh to reload your secure workspace session.
          </p>
          <button
            className="btn-pastel-primary"
            style={{
              background: '#B8C6DB',
              color: '#2D3748',
              border: 'none',
              padding: '12px 28px',
              borderRadius: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
            onClick={() => window.location.reload()}
          >
            Refresh Workspace
          </button>
          {this.state.error && (
            <details style={{ marginTop: '20px', textAlign: 'left' }}>
              <summary style={{ color: '#5A6B7C', cursor: 'pointer', fontSize: '13px' }}>
                Technical Diagnostic Log
              </summary>
              <pre
                style={{
                  background: '#F8F6F4',
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  overflow: 'auto',
                  marginTop: '8px',
                  color: '#2D3748',
                  fontFamily: 'monospace',
                }}
              >
                {this.state.error.message}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
