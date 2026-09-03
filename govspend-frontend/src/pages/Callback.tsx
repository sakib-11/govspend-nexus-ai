import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography } from '@mui/material';
import authService from '../services/auth/authService';
import { useAuthStore } from '../store';
import LoadingSpinner from '../components/common/Loading/LoadingSpinner';
import { toast } from 'react-hot-toast';

export const Callback: React.FC = () => {
  const navigate = useNavigate();
  const { setUser, setAuthenticated, setToken } = useAuthStore();

  useEffect(() => {
    const processCallback = async () => {
      try {
        const oidcUser = await authService.handleCallback();
        if (oidcUser) {
          setToken(oidcUser.access_token);
          setAuthenticated(true);
          toast.success('SSO Authentication successful');
          navigate('/auditor/cases');
          return;
        }
      } catch (err) {
        console.warn('OIDC Callback error, redirecting to home:', err);
      }
      navigate('/auditor/cases');
    };

    processCallback();
  }, [navigate, setUser, setAuthenticated, setToken]);

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <LoadingSpinner message="Completing secure Single Sign-On verification..." />
    </Box>
  );
};

export default Callback;
