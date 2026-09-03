import React, { useState } from 'react';
import {
  Box,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  Grid,
  Slider,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Add as AddIcon,
  CheckCircle as CheckCircleIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';
import { adminService } from '../../../services/api';
import { toast } from 'react-hot-toast';
import { formatDate } from '../../../utils/formatters';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';

export const PolicyManagement: React.FC = () => {
  const [openDialog, setOpenDialog] = useState(false);
  const [description, setDescription] = useState('');
  const [weights, setWeights] = useState({
    price_deviation: 0.30,
    duplicate_fuzzy: 0.20,
    vendor_graph_risk: 0.20,
    timing_anomaly: 0.10,
    contract_splitting: 0.15,
    approval_velocity: 0.05,
  });

  const queryClient = useQueryClient();

  const { data: policies, isLoading } = useQuery({
    queryKey: ['policy-weights'],
    queryFn: () => adminService.getPolicyWeights(),
  });

  const createPolicyMutation = useMutation({
    mutationFn: (data: any) => adminService.createPolicyWeight(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['policy-weights'] });
      toast.success('New policy version published successfully!');
      setOpenDialog(false);
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to create policy');
    },
  });

  const activatePolicyMutation = useMutation({
    mutationFn: (version: string) => adminService.activatePolicyWeight(version),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['policy-weights'] });
      toast.success(`Policy version ${updated.version} is now active in production!`);
    },
  });

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  const isWeightValid = Math.abs(totalWeight - 1.0) < 0.005;

  const handleWeightChange = (key: string, value: number) => {
    setWeights((prev) => ({
      ...prev,
      [key]: Math.round(value * 100) / 100,
    }));
  };

  const handleCreatePolicy = () => {
    if (!isWeightValid) {
      toast.error(`Weights must sum exactly to 1.00 (current: ${totalWeight.toFixed(2)})`);
      return;
    }
    createPolicyMutation.mutate({
      weights,
      description: description || 'Calibrated detector weight version',
      activate: true,
    });
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading policy weights configuration..." />;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Policy Weights & Risk Scoring Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure linear ensemble detector coefficients applied by the core risk scoring engine.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          New Policy Version
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Version</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Weights Breakdown</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Created By</TableCell>
              <TableCell>Created Date</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {policies?.map((policy) => (
              <TableRow key={policy.version} hover>
                <TableCell>
                  <Typography variant="subtitle2" fontWeight={700}>
                    {policy.version}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={policy.is_active ? 'Active (Live)' : 'Inactive'}
                    color={policy.is_active ? 'success' : 'default'}
                    size="small"
                  />
                </TableCell>
                <TableCell sx={{ maxWidth: 450 }}>
                  <Box display="flex" flexWrap="wrap" gap={0.5}>
                    {Object.entries(policy.weights).map(([k, v]) => (
                      <Chip
                        key={k}
                        label={`${k.replace(/_/g, ' ')}: ${(v * 100).toFixed(0)}%`}
                        size="small"
                        variant="outlined"
                      />
                    ))}
                  </Box>
                </TableCell>
                <TableCell>{policy.description || '—'}</TableCell>
                <TableCell>{policy.created_by}</TableCell>
                <TableCell>{formatDate(policy.created_at)}</TableCell>
                <TableCell align="center">
                  <Tooltip title={policy.is_active ? 'Currently Active' : 'Activate this Policy Version'}>
                    <span>
                      <IconButton
                        color={policy.is_active ? 'success' : 'primary'}
                        disabled={policy.is_active || activatePolicyMutation.isPending}
                        onClick={() => activatePolicyMutation.mutate(policy.version)}
                      >
                        <CheckCircleIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create New Policy Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <TuneIcon color="primary" />
            <Typography variant="h6">Calibrate New Policy Weights Version</Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Adjust the weight multipliers for each detector. Total combined sum of all detector weights must equal 1.00 (100%).
          </Typography>

          <Alert
            severity={isWeightValid ? 'success' : 'warning'}
            sx={{ mb: 3 }}
          >
            Combined Weight Total: <strong>{(totalWeight * 100).toFixed(0)}%</strong> ({totalWeight.toFixed(2)} / 1.00)
            {!isWeightValid && ' — Please adjust weights until the total equals 1.00'}
          </Alert>

          <Grid container spacing={3}>
            {Object.entries(weights).map(([key, value]) => (
              <Grid item xs={12} sm={6} key={key}>
                <Typography variant="subtitle2" fontWeight={600} gutterBottom>
                  {key.replace(/_/g, ' ').toUpperCase()}: {(value * 100).toFixed(0)}%
                </Typography>
                <Box display="flex" alignItems="center" gap={2}>
                  <Slider
                    value={value}
                    min={0}
                    max={1}
                    step={0.01}
                    onChange={(_, val) => handleWeightChange(key, val as number)}
                    valueLabelDisplay="auto"
                    valueLabelFormat={(v) => `${(v * 100).toFixed(0)}%`}
                    sx={{ flexGrow: 1 }}
                  />
                  <TextField
                    size="small"
                    type="number"
                    value={value}
                    onChange={(e) => handleWeightChange(key, parseFloat(e.target.value) || 0)}
                    inputProps={{ min: 0, max: 1, step: 0.01 }}
                    sx={{ width: 85 }}
                  />
                </Box>
              </Grid>
            ))}

            <Grid item xs={12}>
              <TextField
                label="Version Changelog / Notes"
                fullWidth
                multiline
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe reason for recalibration (e.g., Increased weight on contract splitting based on audit feedback)"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreatePolicy}
            disabled={!isWeightValid || createPolicyMutation.isPending}
          >
            {createPolicyMutation.isPending ? 'Publishing...' : 'Publish & Activate'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default PolicyManagement;
