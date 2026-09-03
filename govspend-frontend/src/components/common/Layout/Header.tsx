import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Badge,
  Box,
  Menu,
  MenuItem,
  Chip,
  Button,
  Divider,
  Tooltip,
  Avatar,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Notifications as NotificationsIcon,
  AccountCircle,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  SwapHoriz as SwitchRoleIcon,
  Security as SecurityIcon,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import { useAuthStore, useUIStore } from '../../../store';
import authService from '../../../services/auth/authService';

export const Header: React.FC = () => {
  const { user, logout } = useAuthStore();
  const {
    toggleSidebar,
    theme,
    toggleTheme,
    notifications,
    setNotificationDrawerOpen,
    openModal,
  } = useUIStore();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    handleMenuClose();
    logout();
    await authService.logout();
  };

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <AppBar
      position="fixed"
      sx={{
        zIndex: (theme) => theme.zIndex.drawer + 1,
        background: 'rgba(255,255,255,0.78)',
        color: '#1F2A37',
        backdropFilter: 'blur(22px) saturate(160%)',
        WebkitBackdropFilter: 'blur(22px) saturate(160%)',
        borderBottom: '1px solid rgba(148, 163, 184, 0.14)',
        boxShadow: '0 12px 28px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.8)',
        transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      <Toolbar
        sx={{
          minHeight: 76,
          px: { xs: 2, sm: 3 },
          gap: 1,
        }}
      >
        <IconButton
          edge="start"
          onClick={toggleSidebar}
          sx={{
            mr: 1.5,
            bgcolor: 'rgba(91, 124, 153, 0.06)',
            color: '#355999',
            '&:hover': {
              bgcolor: 'rgba(91, 124, 153, 0.12)',
              transform: 'scale(1.06)',
              boxShadow: '0 4px 12px rgba(91, 124, 153, 0.14)',
            },
            transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
          aria-label="Toggle navigation sidebar"
        >
          <MenuIcon />
        </IconButton>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexGrow: 1 }}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #E3ECFF 0%, #D0E4FF 100%)',
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.8), 0 8px 20px rgba(91,124,153,0.16)',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              '&:hover': {
                transform: 'translateY(-2px) rotate(-3deg)',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.9), 0 12px 24px rgba(91,124,153,0.22)',
              },
            }}
          >
            <SecurityIcon sx={{ color: '#355999', fontSize: 24 }} />
          </Box>
          <Box>
            <Typography
              variant="h6"
              component="div"
              sx={{
                fontWeight: 800,
                lineHeight: 1.2,
                color: '#1F2A37',
                fontSize: { xs: '1.1rem', sm: '1.25rem' },
              }}
            >
              GovSpend Nexus AI
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: '#5E6D7D',
                display: { xs: 'none', sm: 'block' },
                fontWeight: 600,
                letterSpacing: '0.01em',
              }}
            >
              Procurement Audit & Risk Intelligence
            </Typography>
          </Box>
        </Box>

        <Button
          variant="outlined"
          size="small"
          startIcon={<SwitchRoleIcon />}
          onClick={() => openModal('roleSwitcher')}
          sx={{
            mr: 1,
            color: '#355999',
            borderColor: 'rgba(91, 124, 153, 0.25)',
            background: 'rgba(91, 124, 153, 0.04)',
            display: { xs: 'none', md: 'inline-flex' },
            '&:hover': {
              borderColor: '#7EA7D7',
              background: 'rgba(126, 167, 215, 0.10)',
              transform: 'translateY(-1px)',
              boxShadow: '0 4px 12px rgba(91, 124, 153, 0.1)',
            },
            transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          Switch Persona
        </Button>

        <Box
          sx={{
            mr: 1,
            textAlign: 'right',
            display: { xs: 'none', sm: 'block' },
          }}
        >
          <Typography variant="body2" sx={{ fontWeight: 700, color: '#1F2A37', lineHeight: 1.3 }}>
            {user?.full_name || 'Auditor'}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: '#5B7C99',
              display: 'block',
              fontWeight: 700,
              fontSize: '0.72rem',
            }}
          >
            {user?.roles?.join(', ')}
          </Typography>
        </Box>

        <Tooltip title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}>
          <IconButton
            onClick={toggleTheme}
            sx={{
              mr: 0.5,
              bgcolor: 'rgba(91, 124, 153, 0.04)',
              color: '#355999',
              '&:hover': {
                bgcolor: 'rgba(91, 124, 153, 0.10)',
                transform: 'scale(1.06)',
                boxShadow: '0 4px 12px rgba(91, 124, 153, 0.12)',
              },
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {theme === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
          </IconButton>
        </Tooltip>

        <Tooltip title="Notifications">
          <IconButton
            onClick={() => setNotificationDrawerOpen(true)}
            sx={{
              mr: 0.5,
              bgcolor: 'rgba(91, 124, 153, 0.04)',
              color: '#355999',
              '&:hover': {
                bgcolor: 'rgba(91, 124, 153, 0.10)',
                transform: 'scale(1.06)',
                boxShadow: '0 4px 12px rgba(91, 124, 153, 0.12)',
              },
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <Badge badgeContent={unreadCount} color="error" sx={{ '& .MuiBadge-badge': { fontWeight: 700 } }}>
              <NotificationsIcon />
            </Badge>
          </IconButton>
        </Tooltip>

        <Tooltip title="Account menu">
          <IconButton
            onClick={handleMenuOpen}
            sx={{
              bgcolor: 'rgba(91, 124, 153, 0.04)',
              color: '#355999',
              '&:hover': {
                bgcolor: 'rgba(91, 124, 153, 0.10)',
                transform: 'scale(1.06)',
                boxShadow: '0 4px 12px rgba(91, 124, 153, 0.12)',
              },
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: 'rgba(91, 124, 153, 0.1)',
                color: '#355999',
                fontWeight: 700,
                fontSize: '0.85rem',
              }}
            >
              {(user?.full_name || 'U').charAt(0)}
            </Avatar>
          </IconButton>
        </Tooltip>

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          PaperProps={{
            sx: {
              width: 280,
              p: 1.5,
              borderRadius: 3,
              boxShadow: '0 20px 48px rgba(15, 23, 42, 0.14)',
              background: 'rgba(255, 255, 255, 0.96)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(148, 163, 184, 0.14)',
            },
          }}
        >
          <Box sx={{ p: 1.5, pb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <Avatar
                sx={{
                  width: 40,
                  height: 40,
                  bgcolor: 'rgba(91, 124, 153, 0.1)',
                  color: '#355999',
                  fontWeight: 700,
                }}
              >
                {(user?.full_name || 'U').charAt(0)}
              </Avatar>
              <Box>
                <Typography variant="subtitle2" fontWeight={800} sx={{ lineHeight: 1.3 }}>
                  {user?.full_name}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.72rem' }}>
                  {user?.email}
                </Typography>
              </Box>
            </Box>
            <Box mt={1.5} display="flex" flexWrap="wrap" gap={0.5}>
              {user?.jurisdictions.map((j) => (
                <Chip
                  key={j}
                  label={j}
                  size="small"
                  variant="outlined"
                  sx={{
                    height: 24,
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    borderRadius: 999,
                    borderColor: 'rgba(148, 163, 184, 0.2)',
                    '&:hover': { borderColor: 'rgba(91, 124, 153, 0.3)' },
                  }}
                />
              ))}
            </Box>
          </Box>
          <Divider sx={{ my: 0.5, borderColor: 'rgba(148, 163, 184, 0.12)' }} />
          <MenuItem
            onClick={() => { handleMenuClose(); openModal('roleSwitcher'); }}
            sx={{
              borderRadius: 1.5,
              mx: 0.5,
              '&:hover': { background: 'rgba(91, 124, 153, 0.06)' },
            }}
          >
            <SwitchRoleIcon fontSize="small" sx={{ mr: 1.5, color: '#355999' }} />
            Switch Persona
          </MenuItem>
          <MenuItem
            onClick={handleLogout}
            sx={{
              color: 'error.main',
              borderRadius: 1.5,
              mx: 0.5,
              '&:hover': { background: 'rgba(199, 111, 111, 0.06)' },
            }}
          >
            <LogoutIcon fontSize="small" sx={{ mr: 1.5 }} />
            Sign Out
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default Header;
