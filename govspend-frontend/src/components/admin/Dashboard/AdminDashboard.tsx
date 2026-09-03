import React from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Security as SecurityIcon,
  AttachMoney as MoneyIcon,
  Speed as SpeedIcon,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { adminService } from '../../../services/api';
import { LoadingSpinner } from '../../common/Loading/LoadingSpinner';
import { formatCurrency } from '../../../utils/formatters';

export const AdminDashboard: React.FC = () => {
  const { data: metrics, isLoading, refetch } = useQuery({
    queryKey: ['admin-metrics'],
    queryFn: () => adminService.getMetrics(),
  });

  if (isLoading || !metrics) {
    return <LoadingSpinner message="Calculating audit metrics and risk telemetry..." />;
  }

  const PIE_COLORS = ['#DC2626', '#D97706', '#16A34A'];

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            System Administration & Risk Intelligence
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real-time multi-detector telemetry, policy weight enforcement, and spend analytics.
          </Typography>
        </Box>
        <Tooltip title="Refresh Telemetry">
          <IconButton
            onClick={() => refetch()}
            color="primary"
            sx={{
              '&:hover': {
                transform: 'scale(1.06)',
                boxShadow: '0 4px 12px rgba(91, 124, 153, 0.14)',
              },
              transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* KPI Cards */}
      <Grid container spacing={3} mb={3}>
        {[
          {
            label: 'Total Cases Audited',
            value: metrics.totalCases,
            icon: <SecurityIcon />,
            color: 'primary',
            accent: '#5B7C99',
            trend: '100% Automated Scanning',
            trendColor: 'success.main',
          },
          {
            label: 'High Risk Flagged',
            value: metrics.highRisk,
            icon: <Chip label="Action Required" color="error" size="small" />,
            color: 'error',
            accent: '#C76F6F',
            trend: 'Critical pricing & network anomalies',
            trendColor: 'text.secondary',
          },
          {
            label: 'Flagged Spend At Risk',
            value: formatCurrency(metrics.potentialSavings),
            icon: <MoneyIcon />,
            color: 'success',
            accent: '#5C9C82',
            trend: `Out of ${formatCurrency(metrics.totalAuditedAmount)} total volume`,
            trendColor: 'text.secondary',
            isCurrency: true,
          },
          {
            label: 'Avg Detection Latency',
            value: `${metrics.avgInferenceLatencyMs}ms`,
            icon: <SpeedIcon />,
            color: 'info',
            accent: '#6D8CC9',
            trend: '99.8% SLA compliant',
            trendColor: 'success.main',
          },
        ].map((kpi, index) => (
          <Grid item xs={12} sm={6} md={3} key={index}>
            <Card
              sx={{
                height: '100%',
                borderLeft: `4px solid ${kpi.accent}`,
                background: 'linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(249,251,255,0.96) 100%)',
                border: `1px solid rgba(148, 163, 184, 0.12)`,
                boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
                transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: '0 16px 40px rgba(15, 23, 42, 0.10), inset 0 1px 0 rgba(255,255,255,1)',
                },
              }}
            >
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="flex-start">
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
                    {typeof kpi.icon === 'string' ? null : kpi.icon}
                  </Box>
                </Box>
                <Typography
                  variant={kpi.isCurrency ? 'h4' : 'h3'}
                  fontWeight={800}
                  mt={1.5}
                  sx={{ letterSpacing: '-0.02em' }}
                >
                  {kpi.value}
                </Typography>
                <Typography
                  variant="caption"
                  color={kpi.trendColor as any}
                  display="flex"
                  alignItems="center"
                  mt={0.75}
                  fontWeight={600}
                >
                  {kpi.trendColor === 'success.main' && <TrendingUpIcon fontSize="small" sx={{ mr: 0.5 }} />}
                  {kpi.trend}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Visualizations Grid */}
      <Grid container spacing={3}>
        {/* Tier Distribution Pie */}
        <Grid item xs={12} md={5}>
          <Paper
            sx={{
              p: 3,
              height: 380,
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
              Cases by Risk Tier
            </Typography>
            <Box sx={{ flexGrow: 1, width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={metrics.tierDistribution}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={4}
                    dataKey="value"
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  >
                    {metrics.tierDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Ingestion & Anomaly Trends */}
        <Grid item xs={12} md={7}>
          <Paper
            sx={{
              p: 3,
              height: 380,
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
              Anomaly Detection Trend (7-Day Rolling)
            </Typography>
            <Box sx={{ flexGrow: 1, width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={metrics.casesOverTime}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <RechartsTooltip />
                  <Legend />
                  <Line type="monotone" dataKey="high" name="High Risk" stroke="#DC2626" strokeWidth={3} />
                  <Line type="monotone" dataKey="borderline" name="Borderline" stroke="#D97706" strokeWidth={2} />
                  <Line type="monotone" dataKey="low" name="Low Risk" stroke="#16A34A" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Detector Performance Bar Chart */}
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
            <Typography variant="h6" fontWeight={700} gutterBottom sx={{ letterSpacing: '-0.01em' }}>
              Detection Volume by Detector Module
            </Typography>
            <Box sx={{ width: '100%', height: 280, mt: 2 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.detectorDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis dataKey="detector" />
                  <YAxis />
                  <RechartsTooltip />
                  <Bar dataKey="count" name="Flagged Signals" fill="#0284C7" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminDashboard;
