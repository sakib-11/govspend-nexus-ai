import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Chip,
  Button,
  Divider,
  LinearProgress,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  Assignment as CaseIcon,
  CheckCircle as ComplianceIcon,
  Warning as AlertIcon,
  Timer as TimerIcon,
  AccountBalance as GovIcon,
} from '@mui/icons-material';
import { officerService } from '../../../services/api';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';
import { formatCurrency, formatRelativeTime } from '../../../utils/formatters';

export const OfficerDashboard: React.FC = () => {
  const navigate = useNavigate();

  const { data: metrics, isLoading } = useQuery({
    queryKey: ['officer-metrics'],
    queryFn: () => officerService.getMetrics(),
  });

  if (isLoading || !metrics) {
    return <LoadingSpinner message="Calculating executive procurement compliance metrics..." />;
  }

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700}>
          Government Officer Executive Portal
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Inter-departmental procurement compliance monitoring, audit status, and high-priority escalation alerts.
        </Typography>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} mb={3}>
        {[
          {
            label: 'Pending Executive Reviews',
            value: metrics.pendingReviews,
            icon: <CaseIcon />,
            color: 'warning',
            accent: '#C78F4A',
            trend: 'Awaiting officer concurrence',
          },
          {
            label: 'Overall Compliance Rate',
            value: `${metrics.complianceRate}%`,
            icon: <ComplianceIcon />,
            color: 'success',
            accent: '#5C9C82',
            trend: 'Target: 90.0% Minimum',
          },
          {
            label: 'Managed Procurement Spend',
            value: formatCurrency(metrics.totalSpendManaged),
            icon: <GovIcon />,
            color: 'primary',
            accent: '#5B7C99',
            trend: `Across ${metrics.totalCases} transactions`,
            isCurrency: true,
          },
          {
            label: 'Avg Audit Resolution',
            value: `${metrics.avgResolutionTime}h`,
            icon: <TimerIcon />,
            color: 'info',
            accent: '#6D8CC9',
            trend: '-4.2h vs prior quarter',
            trendColor: 'success.main',
          },
        ].map((kpi, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Card
              sx={{
                height: '100%',
                borderLeft: `4px solid ${kpi.accent}`,
                background: 'linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(249,251,255,0.96) 100%)',
                border: '1px solid rgba(148, 163, 184, 0.12)',
                boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
                transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: '0 16px 40px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255,255,255,1)',
                },
              }}
            >
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Typography color="text.secondary" variant="subtitle2" fontWeight={600}>
                    {kpi.label}
                  </Typography>
                  <Box
                    sx={{
                      color: kpi.accent,
                      transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                      '&:hover': { transform: 'scale(1.1) rotate(-5deg)' },
                    }}
                  >
                    {kpi.icon}
                  </Box>
                </Box>
                <Typography
                  variant={kpi.isCurrency ? 'h4' : 'h3'}
                  fontWeight={800}
                  mt={1.5}
                  color={kpi.color === 'warning' ? undefined : `${kpi.color}.main`}
                  sx={{ letterSpacing: '-0.02em' }}
                >
                  {kpi.value}
                </Typography>
                <Typography
                  variant="caption"
                  color={kpi.trendColor || 'text.secondary'}
                  display="block"
                  fontWeight={600}
                  mt={0.75}
                >
                  {kpi.trend}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Main Charts & Analytics */}
      <Grid container spacing={3}>
        {/* Cases by Department Stacked Bar */}
        <Grid item xs={12} md={7}>
          <Paper
            sx={{
              p: 3,
              height: 420,
              display: 'flex',
              flexDirection: 'column',
              background: 'linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(249,251,255,0.96) 100%)',
              border: '1px solid rgba(148, 163, 184, 0.12)',
              boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              '&:hover': {
                boxShadow: '0 16px 40px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255,255,255,1)',
                transform: 'translateY(-2px)',
              },
            }}
          >
            <Typography variant="h6" fontWeight={700} gutterBottom sx={{ letterSpacing: '-0.01em' }}>
              Cases by Department & Risk Severity
            </Typography>
            <Box sx={{ flexGrow: 1, width: '100%', height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.casesByDepartment} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis dataKey="department" />
                  <YAxis />
                  <RechartsTooltip />
                  <Legend />
                  <Bar dataKey="high" name="High Risk" stackId="a" fill="#DC2626" />
                  <Bar dataKey="borderline" name="Borderline" stackId="a" fill="#D97706" />
                  <Bar dataKey="low" name="Low Risk" stackId="a" fill="#16A34A" />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Compliance Indicators */}
        <Grid item xs={12} md={5}>
          <Paper
            sx={{
              p: 3,
              height: 420,
              overflow: 'auto',
              background: 'linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(249,251,255,0.96) 100%)',
              border: '1px solid rgba(148, 163, 184, 0.12)',
              boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              '&:hover': {
                boxShadow: '0 16px 40px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255,255,255,1)',
                transform: 'translateY(-2px)',
              },
            }}
          >
            <Typography variant="h6" fontWeight={700} gutterBottom sx={{ letterSpacing: '-0.01em' }}>
              Statutory Compliance Metrics
            </Typography>
            <List dense>
              {metrics.complianceMetrics?.map((metric, idx) => (
                <ListItem
                  key={metric.name}
                  sx={{
                    px: 0,
                    py: 1.5,
                    display: 'block',
                    borderBottom: idx < (metrics.complianceMetrics?.length || 0) - 1 ? '1px solid rgba(148, 163, 184, 0.08)' : 'none',
                  }}
                >
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
                    <Typography variant="subtitle2" fontWeight={600}>
                      {metric.name}
                    </Typography>
                    <Chip
                      label={`${metric.value}% (Target: ${metric.target}%)`}
                      size="small"
                      color={metric.status === 'good' ? 'success' : metric.status === 'fair' ? 'warning' : 'error'}
                      sx={{
                        fontWeight: 700,
                        height: 26,
                        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                        '&:hover': {
                          transform: 'translateY(-1px)',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                        },
                      }}
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                    {metric.description}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={metric.value}
                    color={metric.status === 'good' ? 'success' : metric.status === 'fair' ? 'warning' : 'error'}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      background: 'rgba(148, 163, 184, 0.1)',
                      '& .MuiLinearProgress-bar': {
                        borderRadius: 3,
                        transition: 'all 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
                      },
                    }}
                  />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Critical Alerts Stream */}
        <Grid item xs={12}>
          <Paper
            sx={{
              p: 3,
              background: 'linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(249,251,255,0.96) 100%)',
              border: '1px solid rgba(148, 163, 184, 0.12)',
              boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              '&:hover': {
                boxShadow: '0 16px 40px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255,255,255,1)',
                transform: 'translateY(-2px)',
              },
            }}
          >
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Box display="flex" alignItems="center" gap={1}>
                <AlertIcon color="error" sx={{ fontSize: 28 }} />
                <Typography variant="h6" fontWeight={700}>
                  High-Priority Escalation Alerts
                </Typography>
              </Box>
              <Chip
                label={`${metrics.recentAlerts?.length || 0} Active`}
                color="error"
                size="small"
                sx={{
                  fontWeight: 700,
                  transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  '&:hover': { transform: 'translateY(-1px)' },
                }}
              />
            </Box>

            <List sx={{ p: 0 }}>
              {metrics.recentAlerts?.map((alert, idx) => (
                <ListItem
                  key={alert.id}
                  sx={{
                    p: 2,
                    mb: 1.5,
                    borderRadius: 2.5,
                    border: alert.severity === 'HIGH'
                      ? '1px solid rgba(220, 38, 38, 0.12)'
                      : '1px solid rgba(217, 119, 6, 0.12)',
                    borderLeft: alert.severity === 'HIGH' ? '4px solid rgba(220, 38, 38, 0.35)' : '4px solid rgba(217, 119, 6, 0.35)',
                    bgcolor: alert.severity === 'HIGH' ? 'rgba(254, 226, 226, 0.5)' : 'rgba(254, 243, 199, 0.5)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 1,
                    transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
                    '&:hover': {
                      transform: 'translateX(4px)',
                      boxShadow: '0 8px 20px rgba(15, 23, 42, 0.08)',
                    },
                  }}
                >
                  <Box>
                    <Typography variant="subtitle2" fontWeight={700}>
                      {alert.message}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {alert.department} &bull; Flagged {formatRelativeTime(alert.timestamp)}
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    size="small"
                    color="primary"
                    onClick={() => navigate(`/auditor/cases/${alert.caseId}`)}
                    sx={{
                      borderRadius: 2,
                      fontWeight: 700,
                      transition: 'all 0.22s cubic-bezier(0.16, 1, 0.3, 1)',
                      '&:hover': {
                        transform: 'translateY(-1px)',
                        boxShadow: '0 4px 12px rgba(91, 124, 153, 0.14)',
                      },
                    }}
                  >
                    Inspect Flagged Case
                  </Button>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default OfficerDashboard;
