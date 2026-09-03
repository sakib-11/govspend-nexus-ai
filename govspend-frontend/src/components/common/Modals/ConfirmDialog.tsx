import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  IconButton,
  Box,
  Typography,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: 'primary' | 'error' | 'warning' | 'success';
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmColor = 'primary',
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 4,
          background: 'rgba(255, 255, 255, 0.92)',
          backdropFilter: 'blur(24px) saturate(160%)',
          WebkitBackdropFilter: 'blur(24px) saturate(160%)',
          border: '1px solid rgba(255, 255, 255, 0.32)',
          boxShadow: '0 28px 64px rgba(15, 23, 42, 0.14), inset 0 1px 0 rgba(255,255,255,0.9)',
          overflow: 'hidden',
          position: 'relative',
          '&::before': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, rgba(255,255,255,0.3) 0%, transparent 60%)',
            borderRadius: 'inherit',
            pointerEvents: 'none',
          },
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pb: 1,
          fontWeight: 800,
          letterSpacing: '-0.01em',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <Typography variant="h6" component="span" fontWeight={800}>
          {title}
        </Typography>
        <IconButton
          onClick={onCancel}
          size="small"
          sx={{
            color: '#5E6D7D',
            '&:hover': {
              background: 'rgba(91, 124, 153, 0.06)',
              transform: 'scale(1.06)',
            },
            transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ position: 'relative', zIndex: 1 }}>
        <DialogContentText sx={{ color: '#5E6D7D', lineHeight: 1.6 }}>
          {message}
        </DialogContentText>
      </DialogContent>
      <DialogActions
        sx={{
          px: 3,
          pb: 2.5,
          position: 'relative',
          zIndex: 1,
          gap: 1,
        }}
      >
        <Button
          onClick={onCancel}
          disabled={isLoading}
          sx={{
            borderRadius: 2.5,
            fontWeight: 700,
            transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
            '&:hover': {
              background: 'rgba(91, 124, 153, 0.06)',
              transform: 'translateY(-1px)',
            },
          }}
        >
          {cancelText}
        </Button>
        <Button
          onClick={onConfirm}
          variant="contained"
          color={confirmColor}
          disabled={isLoading}
          sx={{
            borderRadius: 2.5,
            fontWeight: 700,
            boxShadow: '0 8px 20px rgba(91, 124, 153, 0.2)',
            transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: '0 12px 28px rgba(91, 124, 153, 0.28)',
            },
            '&:active': {
              transform: 'translateY(0)',
            },
          }}
        >
          {isLoading ? 'Processing...' : confirmText}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ConfirmDialog;
