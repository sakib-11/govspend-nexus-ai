import React from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Chip,
} from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts';

export const OfficerAnalytics: React.FC = () => {
  const spendTrendData = [
    { month: 'Oct 23', total: 12.4, flagged: 0.8 },
    { month: 'Nov 23', total: 14.1, flagged: 1.1 },
    { month: 'Dec 23', total: 18.5, flagged: 2.3 },
    { month: 'Jan 24', total: 13.2, flagged: 0.9 },
    { month: 'Feb 24', total: 15.6, flagged: 1.4 },
    { month: 'Mar 24', total: 16.8, flagged: 1.2 },
  ];

  const categoryRiskData = [
    { category: 'Heavy Infrastructure', riskVolume: 2.4, transactions: 45 },
    { category: 'IT Software & Cloud', riskVolume: 1.8, transactions: 88 },
    { category: 'Medical & Healthcare', riskVolume: 1.1, transactions: 62 },
    { category: 'Civil Consulting', riskVolume: 0.9, transactions: 31 },
    { category: 'Facilities Management', riskVolume: 0.4, transactions: 22 },
  ];

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700}>
          Procurement Spend & Risk Velocity Analytics
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Deep-dive macroeconomic spend distributions, category concentration indices, and risk anomaly trends.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        {/* Monthly Spend Velocity Area Chart */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3, height: 380, display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Monthly Spend & Flagged Risk Volume ($ Millions)
            </Typography>
            <Box sx={{ flexGrow: 1, width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={spendTrendData}>
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0284C7" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#0284C7" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorFlagged" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#DC2626" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#DC2626" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <RechartsTooltip />
                  <Area type="monotone" dataKey="total" name="Total Spend ($M)" stroke="#0284C7" fillOpacity={1} fill="url(#colorTotal)" />
                  <Area type="monotone" dataKey="flagged" name="Flagged Risk ($M)" stroke="#DC2626" fillOpacity={1} fill="url(#colorFlagged)" />
                </AreaChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Category Risk Bar Chart */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3, height: 380, display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Risk Volume by Procurement Category
            </Typography>
            <Box sx={{ flexGrow: 1, width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryRiskData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                  <XAxis type="number" unit="M" />
                  <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 11 }} />
                  <RechartsTooltip />
                  <Bar dataKey="riskVolume" name="Flagged ($M)" fill="#F59E0B" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Insights Summary Cards */}
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Vendor Concentration Risk
              </Typography>
              <Typography variant="h5" fontWeight={700} mt={1}>
                Top 5 Vendors = 42%
              </Typography>
              <Typography variant="caption" color="text.secondary" mt={0.5} display="block">
                Herfindahl-Hirschman Index: 0.18 (Moderate)
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Price Markup Anomaly Rate
              </Typography>
              <Typography variant="h5" fontWeight={700} color="error.main" mt={1}>
                3.8% of Line Items
              </Typography>
              <Typography variant="caption" color="text.secondary" mt={0.5} display="block">
                Primarily in Road Works and Bitumen supplies
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" color="text.secondary">
                Pre-Payment Interception Rate
              </Typography>
              <Typography variant="h5" fontWeight={700} color="success.main" mt={1}>
                94.6% Intercepted
              </Typography>
              <Typography variant="caption" color="text.secondary" mt={0.5} display="block">
                Flagged before final treasury disbursement
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default OfficerAnalytics;
