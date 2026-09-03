import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Button,
  Chip,
  Paper,
} from '@mui/material';
import {
  Close as CloseIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  CheckCircle as SuccessIcon,
  DeleteSweep as ClearIcon,
} from '@mui/icons-material';
import { useUIStore } from '../../../store';
import { formatRelativeTime } from '../../../utils/formatters';

export const NotificationDrawer: React.FC = () => {
  const navigate = useNavigate();
  const {
    notificationDrawerOpen,
    setNotificationDrawerOpen,
    notifications,
    markNotificationAsRead,
    clearNotifications,
  } = useUIStore();

  const getIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <ErrorIcon color="error" />;
      case 'warning':
        return <WarningIcon color="warning" />;
      case 'success':
        return <SuccessIcon color="success" />;
      default:
        return <InfoIcon color="info" />;
    }
  };

  const getTypeColor = (type: string): string => {
    switch (type) {
      case 'error':
        return 'rgba(199, 111, 111, 0.08)';
      case 'warning':
        return 'rgba(199, 143, 74, 0.08)';
      case 'success':
        return 'rgba(92, 156, 130, 0.08)';
      default:
        return 'rgba(109, 140, 201, 0.08)';
    }
  };

  const handleClickItem = (item: any) => {
    markNotificationAsRead(item.id);
    if (item.link) {
      setNotificationDrawerOpen(false);
      navigate(item.link);
    }
  };

  return (
    <Drawer
      anchor="right"
      open={notificationDrawerOpen}
      onClose={() => setNotificationDrawerOpen(false)}
      sx={{
        '& .MuiDrawer-paper': {
          width: { xs: '100%', sm: 400 },
          p: 0,
          background: 'rgba(255, 255, 255, 0.88)',
          backdropFilter: 'blur(22px) saturate(160%)',
          WebkitBackdropFilter: 'blur(22px) saturate(160%)',
          borderLeft: '1px solid rgba(148, 163, 184, 0.14)',
          boxShadow: '-12px 0 32px rgba(15, 23, 42, 0.08)',
        },
      }}
    >
      <Box
        sx={{
          p: 2.5,
          borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          background: 'rgba(255,255,255,0.6)',
          backdropFilter: 'blur(10px)',
          position: 'sticky',
          top: 0,
          zIndex: 2,
        }}
      >
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Box display="flex" alignItems="center" gap={1.5}>
            <Typography variant="h6" fontWeight={800} sx={{ letterSpacing: '-0.01em' }}>
              Notifications
            </Typography>
            <Chip
              label={notifications.filter((n) => !n.read).length}
              size="small"
              color="primary"
              sx={{
                fontWeight: 700,
                height: 24,
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                '&:hover': { transform: 'translateY(-1px)' },
              }}
            />
          </Box>
          <Box>
            <IconButton
              size="small"
              onClick={clearNotifications}
              title="Clear all"
              sx={{
                '&:hover': {
                  background: 'rgba(91, 124, 153, 0.06)',
                  transform: 'scale(1.06)',
                },
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <ClearIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => setNotificationDrawerOpen(false)}
              sx={{
                '&:hover': {
                  background: 'rgba(91, 124, 153, 0.06)',
                  transform: 'scale(1.06)',
                },
                transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </Box>

      <Divider sx={{ borderColor: 'rgba(148, 163, 184, 0.08)' }} />

      <Box sx={{ flexGrow: 1, overflow: 'auto', p: 1.5 }}>
        {notifications.length === 0 ? (
          <Box py={8} textAlign="center">
            <Typography color="text.secondary" fontWeight={600}>
              No notifications
            </Typography>
            <Typography variant="caption" color="text.disabled">
              You're all caught up!
            </Typography>
          </Box>
        ) : (
          <List sx={{ p: 0 }}>
            {notifications.map((item, idx) => (
              <Paper
                key={item.id}
                onClick={() => handleClickItem(item)}
                sx={{
                  p: 1.5,
                  mb: 1.5,
                  borderRadius: 2.5,
                  bgcolor: item.read ? 'transparent' : getTypeColor(item.type),
                  cursor: 'pointer',
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    background: 'rgba(91, 124, 153, 0.04)',
                    transform: 'translateX(4px)',
                    boxShadow: '0 4px 12px rgba(15, 23, 42, 0.06)',
                  },
                }}
              >
                <ListItem sx={{ p: 0, display: 'flex', alignItems: 'flex-start' }}>
                  <ListItemIcon sx={{ minWidth: 36, mt: 0.25 }}>{getIcon(item.type)}</ListItemIcon>
                  <ListItemText
                    primary={
                      <Typography
                        variant="subtitle2"
                        fontWeight={item.read ? 500 : 700}
                        sx={{ lineHeight: 1.4 }}
                      >
                        {item.title}
                      </Typography>
                    }
                    secondary={
                      <>
                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, lineHeight: 1.5 }}>
                          {item.message}
                        </Typography>
                        <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: 'block' }}>
                          {formatRelativeTime(item.timestamp)}
                        </Typography>
                      </>
                    }
                  />
                </ListItem>
              </Paper>
            ))}
          </List>
        )}
      </Box>
    </Drawer>
  );
};

export default NotificationDrawer;
