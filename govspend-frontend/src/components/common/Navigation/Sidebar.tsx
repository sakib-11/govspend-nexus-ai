import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Toolbar,
  ListSubheader,
  Box,
  Collapse,
  Typography,
} from '@mui/material';
import {
  Assignment as CaseQueueIcon,
  FolderSpecial as MyCasesIcon,
  Hub as VendorGraphIcon,
  Dashboard as DashboardIcon,
  Description as ReportsIcon,
  Insights as AnalyticsIcon,
  AdminPanelSettings as AdminIcon,
  Tune as PolicyIcon,
  People as UsersIcon,
  ReceiptLong as AuditLogIcon,
  Speed as MetricsIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../../store';
import { UserRole } from '../../../types';

interface SidebarProps { open: boolean; }

export const Sidebar: React.FC<SidebarProps> = ({ open }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();

  const isAuditor = user?.roles.some((r) => r.includes('auditor') || r === UserRole.APPROVER);
  const isOfficer = user?.roles.includes(UserRole.OFFICER);
  const isAdmin = user?.roles.some((r) => r === UserRole.ADMIN || r === UserRole.SUPER_ADMIN);

  const getAccentGradient = (route: string): string => {
    if (route.startsWith('/auditor')) {
      return 'linear-gradient(135deg, rgba(190, 220, 255, 0.42), rgba(232, 240, 255, 0.85))';
    }
    if (route.startsWith('/officer/dashboard') || route.startsWith('/officer/reports')) {
      return 'linear-gradient(135deg, rgba(255, 220, 194, 0.42), rgba(255, 246, 234, 0.85))';
    }
    if (route.startsWith('/officer')) {
      return 'linear-gradient(135deg, rgba(203, 229, 212, 0.42), rgba(239, 249, 242, 0.85))';
    }
    return 'linear-gradient(135deg, rgba(203, 229, 212, 0.42), rgba(239, 249, 242, 0.85))';
  };

  const getAccentBorder = (route: string): string => {
    if (route.startsWith('/auditor')) {
      return 'rgba(145, 175, 210, 0.2)';
    }
    if (route.startsWith('/officer')) {
      return 'rgba(223, 185, 137, 0.2)';
    }
    return 'rgba(152, 205, 169, 0.2)';
  };

  const getAccentColor = (route: string): string => {
    if (route.startsWith('/auditor')) return '#5B7C99';
    if (route.startsWith('/officer/dashboard') || route.startsWith('/officer/reports')) return '#C78F4A';
    return '#5C9C82';
  };

  const navItemSx = (path: string) => ({
    minHeight: 48,
    px: 2.2,
    borderRadius: 2.5,
    mx: 0.4,
    transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
    '&.Mui-selected': {
      background: getAccentGradient(path),
      boxShadow: `inset 0 0 0 1px ${getAccentBorder(path)}, 0 2px 8px rgba(91, 124, 153, 0.08)`,
      '&:hover': {
        background: getAccentGradient(path),
      },
    },
    '&:hover': {
      background: 'rgba(91, 124, 153, 0.04)',
      transform: 'translateX(3px)',
    },
  });

  const iconSx = (path: string) => ({
    minWidth: 0,
    mr: open ? 2 : 'auto',
    color: location.pathname.startsWith(path) ? getAccentColor(path) : '#5E6D7D',
    transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
  });

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: open ? 260 : 73,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: open ? 260 : 73,
          boxSizing: 'border-box',
          transition: (theme) =>
            theme.transitions.create('width', {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.enteringScreen,
            }),
          overflowX: 'hidden',
          background: 'linear-gradient(180deg, rgba(248,251,255,0.96) 0%, rgba(244,248,252,0.93) 100%)',
          borderRight: '1px solid rgba(148, 163, 184, 0.14)',
          boxShadow: '8px 0 24px rgba(15, 23, 42, 0.04)',
          backdropFilter: 'blur(12px) saturate(140%)',
          WebkitBackdropFilter: 'blur(12px) saturate(140%)',
        },
      }}
    >
      <Toolbar />
      <Box
        sx={{
          overflow: 'auto',
          mt: 1,
          px: 1.2,
          '&::-webkit-scrollbar': { width: 4 },
          '&::-webkit-scrollbar-thumb': {
            background: 'rgba(148, 163, 184, 0.2)',
            borderRadius: 4,
          },
        }}
      >
        {isAuditor && (
          <>
            {open && (
              <ListSubheader
                sx={{
                  bgcolor: 'transparent',
                  fontWeight: 800,
                  fontSize: '0.68rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.14em',
                  color: '#5E6D7D',
                  py: 1.4,
                  px: 1.8,
                }}
              >
                Auditor Console
              </ListSubheader>
            )}
            <List dense>
              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/auditor/cases' || location.pathname.startsWith('/auditor/cases/')}
                  onClick={() => navigate('/auditor/cases')}
                  sx={navItemSx('/auditor/cases')}
                >
                  <ListItemIcon sx={iconSx('/auditor/cases')}>
                    <CaseQueueIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Case Queue"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/auditor/my-cases'}
                  onClick={() => navigate('/auditor/my-cases')}
                  sx={navItemSx('/auditor/my-cases')}
                >
                  <ListItemIcon sx={iconSx('/auditor/my-cases')}>
                    <MyCasesIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="My Assigned Cases"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/auditor/analytics'}
                  onClick={() => navigate('/auditor/analytics')}
                  sx={navItemSx('/auditor/analytics')}
                >
                  <ListItemIcon sx={iconSx('/auditor/analytics')}>
                    <VendorGraphIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Network Graph"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
            <Divider sx={{ my: 1, borderColor: 'rgba(148, 163, 184, 0.1)' }} />
          </>
        )}

        {isOfficer && (
          <>
            {open && (
              <ListSubheader
                sx={{
                  bgcolor: 'transparent',
                  fontWeight: 800,
                  fontSize: '0.68rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.14em',
                  color: '#5E6D7D',
                  py: 1.4,
                  px: 1.8,
                }}
              >
                Officer Portal
              </ListSubheader>
            )}
            <List dense>
              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/officer/dashboard'}
                  onClick={() => navigate('/officer/dashboard')}
                  sx={navItemSx('/officer/dashboard')}
                >
                  <ListItemIcon sx={iconSx('/officer/dashboard')}>
                    <DashboardIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Executive Dashboard"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/officer/reports'}
                  onClick={() => navigate('/officer/reports')}
                  sx={navItemSx('/officer/reports')}
                >
                  <ListItemIcon sx={iconSx('/officer/reports')}>
                    <ReportsIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Audit Reports"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/officer/analytics'}
                  onClick={() => navigate('/officer/analytics')}
                  sx={navItemSx('/officer/analytics')}
                >
                  <ListItemIcon sx={iconSx('/officer/analytics')}>
                    <AnalyticsIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Spend Analytics"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/officer/institution'}
                  onClick={() => navigate('/officer/institution')}
                  sx={navItemSx('/officer/institution')}
                >
                  <ListItemIcon sx={iconSx('/officer/institution')}>
                    <ReportsIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Submit Invoice"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
            <Divider sx={{ my: 1, borderColor: 'rgba(148, 163, 184, 0.1)' }} />
          </>
        )}

        {isAdmin && (
          <>
            {open && (
              <ListSubheader
                sx={{
                  bgcolor: 'transparent',
                  fontWeight: 800,
                  fontSize: '0.68rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.14em',
                  color: '#5E6D7D',
                  py: 1.4,
                  px: 1.8,
                }}
              >
                Administration
              </ListSubheader>
            )}
            <List dense>
              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/admin/dashboard'}
                  onClick={() => navigate('/admin/dashboard')}
                  sx={navItemSx('/admin/dashboard')}
                >
                  <ListItemIcon sx={iconSx('/admin/dashboard')}>
                    <AdminIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="System Overview"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/admin/policies'}
                  onClick={() => navigate('/admin/policies')}
                  sx={navItemSx('/admin/policies')}
                >
                  <ListItemIcon sx={iconSx('/admin/policies')}>
                    <PolicyIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Policy Weights"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/admin/users'}
                  onClick={() => navigate('/admin/users')}
                  sx={navItemSx('/admin/users')}
                >
                  <ListItemIcon sx={iconSx('/admin/users')}>
                    <UsersIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="User & Jurisdiction"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/admin/audit'}
                  onClick={() => navigate('/admin/audit')}
                  sx={navItemSx('/admin/audit')}
                >
                  <ListItemIcon sx={iconSx('/admin/audit')}>
                    <AuditLogIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Hash-Chain Audit"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>

              <ListItem disablePadding sx={{ display: 'block' }}>
                <ListItemButton
                  selected={location.pathname === '/admin/metrics'}
                  onClick={() => navigate('/admin/metrics')}
                  sx={navItemSx('/admin/metrics')}
                >
                  <ListItemIcon sx={iconSx('/admin/metrics')}>
                    <MetricsIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="System Metrics"
                    sx={{
                      opacity: open ? 1 : 0,
                      transition: 'opacity 0.22s ease',
                      '& .MuiTypography-root': { fontWeight: 700, fontSize: '0.9rem' },
                    }}
                  />
                </ListItemButton>
              </ListItem>
            </List>
          </>
        )}
      </Box>
    </Drawer>
  );
};

export default Sidebar;
