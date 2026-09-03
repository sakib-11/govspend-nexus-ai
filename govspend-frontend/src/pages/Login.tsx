import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Divider,
  Container,
  Stack,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Login as LoginIcon,
  AdminPanelSettings as AdminIcon,
  AssignmentTurnedIn as AuditorIcon,
  AccountBalance as OfficerIcon,
  VerifiedUser as ShieldIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../store';
import { DEMO_USERS } from '../store/slices/authSlice';
import authService from '../services/auth/authService';
import { toast } from 'react-hot-toast';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { loginAsDemoUser } = useAuthStore();

  const handleOidcLogin = async () => {
    toast.loading('Redirecting to Government OIDC Authority...');
    await authService.login();
  };

  const handleSelectDemoUser = (key: keyof typeof DEMO_USERS) => {
    loginAsDemoUser(key);
    const demo = DEMO_USERS[key];
    toast.success(`Logged in as ${demo.full_name}`);

    if (demo.roles.some((r) => r.includes('admin'))) {
      navigate('/admin/dashboard');
    } else if (demo.roles.includes('officer' as any)) {
      navigate('/officer/dashboard');
    } else {
      navigate('/auditor/cases');
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background:
          'radial-gradient(ellipse at 10% 20%, rgba(186, 230, 253, 0.45), transparent 38%), radial-gradient(ellipse at 90% 15%, rgba(216, 180, 254, 0.32), transparent 32%), radial-gradient(ellipse at 50% 90%, rgba(253, 224, 71, 0.16), transparent 28%), #F7FAFC',
        position: 'relative',
        p: { xs: 2, md: 4 },
        overflow: 'hidden',
      }}
    >
      {/* Ambient orbs */}
      <Box
        className="ambient-orb primary"
        sx={{
          position: 'absolute',
          width: { xs: 260, md: 420 },
          height: { xs: 260, md: 420 },
          top: 40,
          left: { xs: 60, md: 100 },
          zIndex: 0,
          pointerEvents: 'none',
        }}
      />
      <Box
        className="ambient-orb secondary"
        sx={{
          position: 'absolute',
          width: { xs: 200, md: 340 },
          height: { xs: 200, md: 340 },
          right: { xs: 40, md: 80 },
          bottom: { xs: 60, md: 100 },
          zIndex: 0,
          pointerEvents: 'none',
        }}
      />
      <Box
        className="ambient-orb accent"
        sx={{
          position: 'absolute',
          width: { xs: 160, md: 260 },
          height: { xs: 160, md: 260 },
          bottom: { xs: 120, md: 180 },
          left: '40%',
          zIndex: 0,
          pointerEvents: 'none',
        }}
      />

      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
        <Paper
          elevation={0}
          sx={{
            p: { xs: 3, sm: 4, md: 6 },
            borderRadius: 5,
            bgcolor: 'rgba(255,255,255,0.82)',
            border: '1px solid rgba(255, 255, 255, 0.32)',
            boxShadow: '0 30px 80px rgba(15, 23, 42, 0.12), inset 0 1px 0 rgba(255,255,255,0.9)',
            backdropFilter: 'blur(20px) saturate(160%)',
            WebkitBackdropFilter: 'blur(20px) saturate(160%)',
            position: 'relative',
            overflow: 'hidden',
            '&::before': {
              content: '""',
              position: 'absolute',
              inset: 0,
              background: 'linear-gradient(135deg, rgba(255,255,255,0.4) 0%, transparent 60%)',
              borderRadius: 'inherit',
              pointerEvents: 'none',
            },
          }}
        >
          <Box textAlign="center" mb={5}>
            <Box display="flex" justifyContent="center" alignItems="center" gap={1.5} mb={2.5}>
              <Box
                sx={{
                  width: 56,
                  height: 56,
                  borderRadius: '18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg, #E3ECFF 0%, #D0E4FF 100%)',
                  boxShadow: 'inset 0 2px 0 rgba(255,255,255,0.9), 0 14px 28px rgba(91,124,153,0.2)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    transform: 'translateY(-3px) rotate(-4deg)',
                    boxShadow: 'inset 0 2px 0 rgba(255,255,255,1), 0 18px 36px rgba(91,124,153,0.28)',
                  },
                }}
              >
                <SecurityIcon sx={{ fontSize: 32, color: '#355999' }} />
              </Box>
              <Typography
                variant="h3"
                sx={{
                  fontWeight: 900,
                  letterSpacing: '-0.06em',
                  color: '#234B78',
                  fontSize: { xs: '1.75rem', sm: '2.25rem', md: '2.75rem' },
                }}
              >
                GovSpend Nexus AI
              </Typography>
            </Box>

            <Typography
              variant="h6"
              color="text.secondary"
              sx={{
                fontWeight: 600,
                maxWidth: 760,
                mx: 'auto',
                lineHeight: 1.6,
                fontSize: { xs: '0.95rem', sm: '1.05rem' },
              }}
            >
              Government Spend Audit & Procurement Risk Intelligence System
            </Typography>

            <Stack direction="row" spacing={1} justifyContent="center" mt={3} flexWrap="wrap" useFlexGap>
              <Chip
                icon={<ShieldIcon />}
                label="Tamper-Evident Hash Chain"
                size="small"
                sx={{
                  fontWeight: 600,
                  background: 'rgba(91, 124, 153, 0.06)',
                  border: '1px solid rgba(91, 124, 153, 0.12)',
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    background: 'rgba(91, 124, 153, 0.10)',
                    transform: 'translateY(-1px)',
                    boxShadow: '0 4px 12px rgba(91, 124, 153, 0.1)',
                  },
                }}
              />
              <Chip
                label="Dual-Control Unmasking"
                size="small"
                variant="outlined"
                sx={{
                  fontWeight: 600,
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    background: 'rgba(91, 124, 153, 0.04)',
                    transform: 'translateY(-1px)',
                    boxShadow: '0 4px 12px rgba(91, 124, 153, 0.08)',
                  },
                }}
              />
              <Chip
                label="RAG-Grounded AI Explanations"
                size="small"
                color="success"
                sx={{
                  fontWeight: 600,
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    transform: 'translateY(-1px)',
                    boxShadow: '0 4px 12px rgba(92, 156, 130, 0.14)',
                  },
                }}
              />
            </Stack>
          </Box>

          <Box mb={4} textAlign="center">
            <Button
              variant="contained"
              size="large"
              startIcon={<LoginIcon />}
              onClick={handleOidcLogin}
              sx={{
                py: 1.6,
                px: 5,
                fontSize: '1.08rem',
                borderRadius: 3,
                background: 'linear-gradient(135deg, #B7D1F0 0%, #7EA7D7 100%)',
                color: '#173553',
                boxShadow: '0 18px 32px rgba(126, 167, 215, 0.32), inset 0 1px 0 rgba(255,255,255,0.3)',
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  inset: 0,
                  background: 'linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 60%)',
                  borderRadius: 'inherit',
                  pointerEvents: 'none',
                },
                '&:hover': {
                  background: 'linear-gradient(135deg, #A9C4E9 0%, #6D98CC 100%)',
                  boxShadow: '0 24px 40px rgba(126, 167, 215, 0.40), inset 0 1px 0 rgba(255,255,255,0.4)',
                  transform: 'translateY(-2px)',
                },
                '&:active': {
                  transform: 'translateY(0)',
                  boxShadow: '0 10px 20px rgba(126, 167, 215, 0.24), inset 0 1px 0 rgba(255,255,255,0.2)',
                },
                position: 'relative',
                overflow: 'hidden',
                transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              Sign In with Government SSO (OIDC / PKCE)
            </Button>
          </Box>

          <Divider
            sx={{
              my: 3.5,
              '&::before, &::after': {
                borderColor: 'rgba(148, 163, 184, 0.24)',
              },
            }}
          >
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                px: 2,
                fontWeight: 700,
                letterSpacing: '0.14em',
                fontSize: '0.78rem',
              }}
            >
              OR TEST INSTANTLY WITH ROLE PERSONAS
            </Typography>
          </Divider>

          <Grid container spacing={2.5}>
            <Grid item xs={12} sm={6} md={4}>
              <Card
                sx={{
                  height: '100%',
                  borderColor: 'rgba(211, 126, 126, 0.34)',
                  background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(255,245,245,0.96) 100%)',
                  boxShadow: '0 12px 28px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
                  border: '1px solid rgba(211, 126, 126, 0.2)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: '0 20px 44px rgba(199, 111, 111, 0.12), inset 0 1px 0 rgba(255,255,255,1)',
                    borderColor: 'rgba(211, 126, 126, 0.38)',
                  },
                }}
              >
                <CardActionArea onClick={() => handleSelectDemoUser('super_admin')} sx={{ height: '100%', p: 1.5 }}>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1" fontWeight={800} color="error.main">
                        Super Admin
                      </Typography>
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: 'linear-gradient(135deg, #F9E4E4 0%, #F0CACA 100%)',
                          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.6), 0 6px 16px rgba(199, 111, 111, 0.14)',
                        }}
                      >
                        <AdminIcon sx={{ color: '#7A3E3E', fontSize: 22 }} />
                      </Box>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      Full system administration, cryptographic audit ledgers, policy weighting, and dual-control approval.
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={4}>
              <Card
                sx={{
                  height: '100%',
                  borderColor: 'rgba(91, 124, 153, 0.34)',
                  background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(240,246,255,0.96) 100%)',
                  boxShadow: '0 12px 28px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
                  border: '1px solid rgba(91, 124, 153, 0.2)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: '0 20px 44px rgba(91, 124, 153, 0.12), inset 0 1px 0 rgba(255,255,255,1)',
                    borderColor: 'rgba(91, 124, 153, 0.38)',
                  },
                }}
              >
                <CardActionArea onClick={() => handleSelectDemoUser('auditor_l3')} sx={{ height: '100%', p: 1.5 }}>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1" fontWeight={800} color="primary.main">
                        Senior Auditor (L3)
                      </Typography>
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: 'linear-gradient(135deg, #D9E7F4 0%, #C4D9EC 100%)',
                          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.6), 0 6px 16px rgba(91, 124, 153, 0.14)',
                        }}
                      >
                        <AuditorIcon sx={{ color: '#2E455C', fontSize: 22 }} />
                      </Box>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      Case review, evidence inspection, AI RAG explanations, maker unmask requests, and case approvals.
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>

            <Grid item xs={12} sm={6} md={4}>
              <Card
                sx={{
                  height: '100%',
                  borderColor: 'rgba(199, 143, 74, 0.34)',
                  background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(255,249,240,0.96) 100%)',
                  boxShadow: '0 12px 28px rgba(15, 23, 42, 0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
                  border: '1px solid rgba(199, 143, 74, 0.2)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: '0 20px 44px rgba(199, 143, 74, 0.12), inset 0 1px 0 rgba(255,255,255,1)',
                    borderColor: 'rgba(199, 143, 74, 0.38)',
                  },
                }}
              >
                <CardActionArea onClick={() => handleSelectDemoUser('officer')} sx={{ height: '100%', p: 1.5 }}>
                  <CardContent>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1" fontWeight={800} color="warning.main">
                        Government Officer
                      </Typography>
                      <Box
                        sx={{
                          width: 40,
                          height: 40,
                          borderRadius: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: 'linear-gradient(135deg, #F6E8CB 0%, #EFD9A3 100%)',
                          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.6), 0 6px 16px rgba(199, 143, 74, 0.14)',
                        }}
                      >
                        <OfficerIcon sx={{ color: '#83591A', fontSize: 22 }} />
                      </Box>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      Executive dashboard, department compliance scorecards, audit reports, and critical anomaly alerts.
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          </Grid>
        </Paper>
      </Container>
    </Box>
  );
};

export default Login;
