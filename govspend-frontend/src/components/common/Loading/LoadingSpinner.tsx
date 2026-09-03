import React from 'react';
import { Box, Typography } from '@mui/material';

interface LoadingSpinnerProps {
  message?: string;
  size?: number;
  minHeight?: number | string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Loading data...',
  size = 48,
  minHeight = '200px',
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight,
        gap: 2.5,
        p: 3,
        animation: 'fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      }}
    >
      <Box
        sx={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: 'rgba(255, 255, 255, 0.72)',
          backdropFilter: 'blur(10px)',
          border: '3px solid rgba(148, 163, 184, 0.12)',
          borderTopColor: '#5B7C99',
          animation: 'spin 0.8s linear infinite',
          boxShadow: '0 8px 24px rgba(91, 124, 153, 0.12), inset 0 1px 0 rgba(255,255,255,0.7)',
          position: 'relative',
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: '8px',
            borderRadius: '50%',
            border: '2px solid rgba(148, 163, 184, 0.06)',
            borderTopColor: 'rgba(91, 124, 153, 0.15)',
            animation: 'spin 1.2s linear infinite reverse',
          },
        }}
      />
      {message && (
        <Typography
          variant="body2"
          sx={{
            color: '#5E6D7D',
            fontWeight: 600,
            letterSpacing: '0.01em',
            animation: 'pulse 2s ease-in-out infinite',
          }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );
};

export default LoadingSpinner;
