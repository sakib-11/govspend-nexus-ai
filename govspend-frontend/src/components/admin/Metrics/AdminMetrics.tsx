import React from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  Speed as SpeedIcon,
  Memory as MemoryIcon,
  CloudDone as CloudDoneIcon,
} from '@mui/icons-material';

export const AdminMetrics: React.FC = () => {
  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700}>
          Engine Infrastructure & Telemetry
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Microservice health, inference latency, cache hit ratios, and ingestion throughput.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <SpeedIcon color="primary" />
                <Typography variant="subtitle2">RAG Retriever Latency</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>
                42ms
              </Typography>
              <Box mt={2}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption">Vector Search SLA</Typography>
                  <Typography variant="caption" color="success.main">99.4%</Typography>
                </Box>
                <LinearProgress variant="determinate" value={99.4} color="success" />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <MemoryIcon color="info" />
                <Typography variant="subtitle2">LLM Explanation Engine</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>
                310ms
              </Typography>
              <Box mt={2}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption">Grounding Score</Typography>
                  <Typography variant="caption" color="success.main">98.5%</Typography>
                </Box>
                <LinearProgress variant="determinate" value={98.5} color="primary" />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <CloudDoneIcon color="success" />
                <Typography variant="subtitle2">Hash-Chain Ingestion Rate</Typography>
              </Box>
              <Typography variant="h4" fontWeight={700}>
                1,420 tx/s
              </Typography>
              <Box mt={2}>
                <Box display="flex" justifyContent="space-between" mb={0.5}>
                  <Typography variant="caption">Zero-Loss Verification</Typography>
                  <Typography variant="caption" color="success.main">100%</Typography>
                </Box>
                <LinearProgress variant="determinate" value={100} color="success" />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Registered Microservice Endpoints
            </Typography>
            <List dense>
              {[
                { name: 'ingestion-svc', url: 'http://localhost:8001/health', status: 'Healthy', load: '14%' },
                { name: 'detection-core', url: 'http://localhost:8002/health', status: 'Healthy', load: '32%' },
                { name: 'evidence-bundle-svc', url: 'http://localhost:8003/health', status: 'Healthy', load: '21%' },
                { name: 'explanation-svc', url: 'http://localhost:8004/health', status: 'Healthy', load: '45%' },
                { name: 'audit-hashchain-svc', url: 'http://localhost:8005/health', status: 'Healthy', load: '8%' },
                { name: 'unmask-svc', url: 'http://localhost:8006/health', status: 'Healthy', load: '4%' },
              ].map((svc) => (
                <ListItem key={svc.name} divider>
                  <ListItemText
                    primary={svc.name}
                    secondary={svc.url}
                  />
                  <Box textAlign="right">
                    <Typography variant="body2" color="success.main" fontWeight={600}>
                      {svc.status}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Load: {svc.load}
                    </Typography>
                  </Box>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Ensemble Model Weight Versioning
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              The active detector ensemble configuration applies calibrated linear scoring with strict bounding.
            </Typography>
            <List dense>
              <ListItem divider>
                <ListItemText primary="Active Version" secondary="v2.1 (Calibrated)" />
              </ListItem>
              <ListItem divider>
                <ListItemText primary="Confidence Calibration" secondary="Platt Scaling (Sigmoid fitted on historical ground truth)" />
              </ListItem>
              <ListItem divider>
                <ListItemText primary="Dual-Control Enforcement" secondary="Active (Requires Maker + Checker authorization)" />
              </ListItem>
              <ListItem>
                <ListItemText primary="Jurisdiction Scope" secondary="Multi-Jurisdiction Federal & State Isolation" />
              </ListItem>
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminMetrics;
