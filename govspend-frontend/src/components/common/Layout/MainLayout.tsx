import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box, Toolbar } from '@mui/material';
import { useUIStore } from '../../../store';
import Header from './Header';
import Sidebar from '../Navigation/Sidebar';
import NotificationDrawer from '../Modals/NotificationDrawer';
import RoleSwitcherModal from '../Auth/RoleSwitcherModal';
import { useLiveAlerts } from '../../../hooks/useLiveAlerts';

export const MainLayout: React.FC = () => {
  const { sidebarOpen } = useUIStore();
  useLiveAlerts();

  return (
    <Box
      sx={{
        display: 'flex',
        minHeight: '100vh',
        background:
          'radial-gradient(circle at top left, rgba(186, 230, 253, 0.24), transparent 26%), radial-gradient(circle at bottom right, rgba(216, 180, 254, 0.18), transparent 24%), #F7FAFC',
        position: 'relative',
      }}
    >
      {/* Ambient depth orbs */}
      <Box
        className="ambient-orb primary"
        sx={{
          position: 'fixed',
          width: { xs: 260, md: 420 },
          height: { xs: 260, md: 420 },
          top: -60,
          left: -40,
          zIndex: 0,
          pointerEvents: 'none',
          opacity: 0.4,
        }}
      />
      <Box
        className="ambient-orb secondary"
        sx={{
          position: 'fixed',
          width: { xs: 200, md: 360 },
          height: { xs: 200, md: 360 },
          bottom: -40,
          right: -30,
          zIndex: 0,
          pointerEvents: 'none',
          opacity: 0.35,
        }}
      />

      <Box sx={{ position: 'relative', zIndex: 1, width: '100%', display: 'flex' }}>
        <Header />
        <Sidebar open={sidebarOpen} />

        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: { xs: 1.5, sm: 2.5, md: 3 },
            width: { sm: `calc(100% - ${sidebarOpen ? 260 : 73}px)` },
            transition: (theme) =>
              theme.transitions.create(['width', 'margin'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
              }),
            overflow: 'auto',
            position: 'relative',
            minHeight: '100vh',
          }}
        >
          <Toolbar />
          <Box
            sx={{
              position: 'relative',
              borderRadius: 3,
              minHeight: 'calc(100vh - 96px)',
              p: { xs: 0.5, sm: 1 },
            }}
          >
            <Outlet />
          </Box>
        </Box>
      </Box>

      <NotificationDrawer />
      <RoleSwitcherModal />
    </Box>
  );
};

export default MainLayout;
