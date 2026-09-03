import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { SnackbarProvider } from 'notistack';
import { Toaster } from 'react-hot-toast';
import { queryClient } from './services/api/queryClient';
import { getTheme } from './styles/theme';
import { useAuthStore, useUIStore } from './store';
import MainLayout from './components/common/Layout/MainLayout';
import ProtectedRoute from './components/common/Auth/ProtectedRoute';
import Login from './pages/Login';
import Callback from './pages/Callback';
import AdminRoutes from './pages/Admin/AdminRoutes';
import AuditorRoutes from './pages/Auditor/AuditorRoutes';
import OfficerRoutes from './pages/Officer/OfficerRoutes';
import PublicTransparency from './pages/PublicTransparency';

export const App: React.FC = () => {
  const { user } = useAuthStore();
  const { theme: themeMode } = useUIStore();

  const currentTheme = getTheme(themeMode);

  const getDefaultRoute = () => {
    if (!user) return '/login';
    if (user.roles.some((r) => r === 'admin' || r === 'super_admin')) {
      return '/admin/dashboard';
    }
    if (user.roles.includes('officer' as any)) {
      return '/officer/dashboard';
    }
    return '/auditor/cases';
  };

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={currentTheme}>
        <CssBaseline />
        <SnackbarProvider maxSnack={3}>
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: themeMode === 'dark' ? '#1E293B' : '#FFFFFF',
                color: themeMode === 'dark' ? '#F8FAFC' : '#0F172A',
                border: themeMode === 'dark' ? '1px solid #334155' : '1px solid #E2E8F0',
              },
            }}
          />
          <BrowserRouter>
            <Routes>
              <Route path="/transparency" element={<PublicTransparency />} />
              <Route path="/login" element={<Login />} />
              <Route path="/callback" element={<Callback />} />

              <Route element={<ProtectedRoute />}>
                <Route element={<MainLayout />}>
                  <Route path="/admin/*" element={<AdminRoutes />} />
                  <Route path="/auditor/*" element={<AuditorRoutes />} />
                  <Route path="/officer/*" element={<OfficerRoutes />} />
                  <Route path="/" element={<Navigate to={getDefaultRoute()} replace />} />
                </Route>
              </Route>

              {/* Catch-all fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SnackbarProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;
