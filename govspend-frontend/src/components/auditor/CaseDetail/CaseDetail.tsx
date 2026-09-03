import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  Chip,
  Button,
  Divider,
  IconButton,
  Tooltip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ExpandMore as ExpandMoreIcon,
  Refresh as RefreshIcon,
  CheckCircle as ApproveIcon,
  Cancel as RejectIcon,
  Flag as EscalateIcon,
  LockOpen as LockOpenIcon,
  ArrowBack as BackIcon,
  DoneAll as CloseCaseIcon,
} from '@mui/icons-material';
import { caseService, explanationService } from '../../../services/api';
import { useAuthStore, useUIStore } from '../../../store';
import {
  formatCurrency,
  formatDate,
  formatRiskScore,
  getTierColor,
  getStatusColor,
} from '../../../utils/formatters';
import ExplanationPanel from '../ExplanationPanel/ExplanationPanel';
import VendorGraph from '../VendorGraph/VendorGraph';
import UnmaskModal from '../UnmaskModal/UnmaskModal';
import EvidenceViewer from './EvidenceViewer';
import SignalBreakdown from './SignalBreakdown';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';
import { toast } from 'react-hot-toast';

export const CaseDetail: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { openModal } = useUIStore();

  const [actionNotes, setActionNotes] = useState('');
  const [showActionDialog, setShowActionDialog] = useState(false);
  const [actionType, setActionType] = useState<'approve' | 'reject' | 'escalate' | 'close'>('approve');

  // Fetch case detail
  const { data: detailData, isLoading, refetch } = useQuery({
    queryKey: ['case-detail', caseId],
    queryFn: () => caseService.getCaseDetail(caseId!),
    enabled: !!caseId,
  });

  // Fetch explanation
  const { data: explanation } = useQuery({
    queryKey: ['explanation', caseId],
    queryFn: () => explanationService.getExplanation(caseId!),
    enabled: !!caseId,
  });

  // Action mutations
  const performActionMutation = useMutation({
    mutationFn: (action: 'approve' | 'reject' | 'escalate' | 'close') => {
      if (action === 'approve') return caseService.approveCase(caseId!, { notes: actionNotes });
      if (action === 'reject') return caseService.rejectCase(caseId!, { notes: actionNotes });
      if (action === 'escalate') return caseService.escalateCase(caseId!, { notes: actionNotes });
      return caseService.closeCase(caseId!, { notes: actionNotes });
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['case-detail', caseId] });
      queryClient.invalidateQueries({ queryKey: ['cases'] });
      toast.success(res?.message || `Case action [${actionType}] completed successfully`);
      setShowActionDialog(false);
      setActionNotes('');
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to complete case action');
    },
  });

  const handleTriggerAction = (action: 'approve' | 'reject' | 'escalate' | 'close') => {
    setActionType(action);
    setShowActionDialog(true);
  };

  const handleConfirmAction = () => {
    performActionMutation.mutate(actionType);
  };

  if (isLoading) {
    return <LoadingSpinner message="Retrieving case details and evidence bundles..." />;
  }

  if (!detailData || !detailData.case) {
    return (
      <Box p={3}>
        <Alert severity="error">Case {caseId} not found.</Alert>
        <Button startIcon={<BackIcon />} onClick={() => navigate('/auditor/cases')} sx={{ mt: 2 }}>
          Return to Queue
        </Button>
      </Box>
    );
  }

  const { case: caseData, evidence, actions } = detailData;

  return (
    <Box>
      {/* Top Breadcrumb & Action Bar */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexWrap="wrap" gap={2}>
        <Box display="flex" alignItems="center" gap={2}>
          <IconButton onClick={() => navigate('/auditor/cases')}>
            <BackIcon />
          </IconButton>
          <Box>
            <Box display="flex" alignItems="center" gap={1}>
              <Typography variant="h4" fontWeight={700}>
                Case {caseData.case_id.toUpperCase()}
              </Typography>
              <Chip
                label={formatRiskScore(caseData.risk_score)}
                color={getTierColor(caseData.tier)}
                sx={{ fontWeight: 700 }}
              />
              <Chip
                label={caseData.tier}
                color={getTierColor(caseData.tier)}
                variant="outlined"
              />
              <Chip
                label={caseData.status}
                color={getStatusColor(caseData.status)}
              />
            </Box>
            <Typography variant="caption" color="text.secondary">
              Transaction ID: {caseData.transaction_id} • Created: {formatDate(caseData.created_at)}
            </Typography>
          </Box>
        </Box>

        {/* Action Buttons */}
        <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
          <Tooltip title="Refresh Case">
            <IconButton onClick={() => refetch()} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Button
            variant="outlined"
            color="primary"
            startIcon={<LockOpenIcon />}
            onClick={() => openModal('unmask', { entityToken: caseData.vendor.vendor_token })}
          >
            Request Unmask
          </Button>

          {caseData.status !== 'APPROVED' && (
            <Button
              variant="contained"
              color="success"
              startIcon={<ApproveIcon />}
              onClick={() => handleTriggerAction('approve')}
            >
              Approve
            </Button>
          )}

          {caseData.status !== 'REJECTED' && (
            <Button
              variant="contained"
              color="error"
              startIcon={<RejectIcon />}
              onClick={() => handleTriggerAction('reject')}
            >
              Reject
            </Button>
          )}

          {caseData.status !== 'ESCALATED' && (
            <Button
              variant="contained"
              color="warning"
              startIcon={<EscalateIcon />}
              onClick={() => handleTriggerAction('escalate')}
            >
              Escalate
            </Button>
          )}

          {caseData.status !== 'CLOSED' && (
            <Button
              variant="outlined"
              color="inherit"
              startIcon={<CloseCaseIcon />}
              onClick={() => handleTriggerAction('close')}
            >
              Close
            </Button>
          )}
        </Box>
      </Box>

      {/* Transaction & Signals Overview */}
      <Grid container spacing={3} mb={3}>
        {/* Transaction Summary Card */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h6" fontWeight={700} gutterBottom>
                Transaction & Vendor Profile
              </Typography>
              <Divider sx={{ my: 1.5 }} />

              <Box display="flex" flexDirection="column" gap={1.5}>
                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Department / Agency:</Typography>
                  <Typography variant="subtitle2" fontWeight={600}>
                    {caseData.department.department_name}
                  </Typography>
                </Box>
                <Divider />

                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Vendor Token:</Typography>
                  <Box display="flex" alignItems="center" gap={0.5}>
                    <Typography variant="subtitle2" fontFamily="monospace" fontWeight={700}>
                      {caseData.vendor.vendor_token}
                    </Typography>
                    <Chip label="Masked" size="small" variant="outlined" />
                  </Box>
                </Box>
                <Divider />

                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Total Billed Amount:</Typography>
                  <Typography variant="subtitle1" fontWeight={700} color="primary.main">
                    {formatCurrency(caseData.transaction.amount)}
                  </Typography>
                </Box>
                <Divider />

                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Unit Rate & Volume:</Typography>
                  <Typography variant="body2">
                    {formatCurrency(caseData.transaction.unit_price || 0)} × {caseData.transaction.quantity || 1} units
                  </Typography>
                </Box>
                <Divider />

                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Procurement Category:</Typography>
                  <Typography variant="body2">{caseData.transaction.category || 'General Supplies'}</Typography>
                </Box>
                <Divider />

                <Box display="flex" justifyContent="space-between">
                  <Typography variant="body2" color="text.secondary">Ingestion Source & Hash:</Typography>
                  <Typography variant="caption" fontFamily="monospace" color="text.secondary">
                    {caseData.transaction.source || 'ERP Ingestion'}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Signals Breakdown Card */}
        <Grid item xs={12} md={6}>
          <SignalBreakdown signals={caseData.signals} />
        </Grid>
      </Grid>

      {/* AI Grounded Explanation */}
      {explanation && <ExplanationPanel explanation={explanation} />}

      {/* Evidence Viewer */}
      <EvidenceViewer evidence={evidence} />

      {/* Vendor Network Graph Accordion */}
      <Paper sx={{ mb: 3 }}>
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6" fontWeight={700}>
              Interactive Vendor Relationship & Shell Entity Graph
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            <VendorGraph vendorToken={caseData.vendor.vendor_token} />
          </AccordionDetails>
        </Accordion>
      </Paper>

      {/* Audit Action History Timeline */}
      {actions && actions.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={700} gutterBottom>
              Case Action & Audit History ({actions.length})
            </Typography>
            <Divider sx={{ my: 1 }} />

            <Box display="flex" flexDirection="column" gap={1.5} mt={1}>
              {actions.map((act) => (
                <Box
                  key={act.action_id}
                  sx={{
                    p: 1.5,
                    borderRadius: 1.5,
                    borderLeft: 4,
                    borderColor: 'primary.main',
                    bgcolor: 'action.hover',
                  }}
                >
                  <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2" fontWeight={700}>
                      {act.action.replace(/_/g, ' ')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(act.action_time)} by {act.user_id}
                    </Typography>
                  </Box>
                  {act.notes && (
                    <Typography variant="body2" color="text.secondary" mt={0.5}>
                      {act.notes}
                    </Typography>
                  )}
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Action Dialog */}
      <Dialog open={showActionDialog} onClose={() => setShowActionDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Confirm Case Action: {actionType.toUpperCase()}
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" mb={2}>
            Please provide optional audit rationale or decision notes for recording into the immutable audit trail.
          </Typography>
          <TextField
            label="Auditor Notes / Resolution Findings"
            multiline
            rows={3}
            fullWidth
            value={actionNotes}
            onChange={(e) => setActionNotes(e.target.value)}
            placeholder="e.g. Verified market benchmark documentation; price deviation is within approved emergency variance range."
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setShowActionDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            color={
              actionType === 'approve'
                ? 'success'
                : actionType === 'reject'
                ? 'error'
                : actionType === 'escalate'
                ? 'warning'
                : 'primary'
            }
            onClick={handleConfirmAction}
            disabled={performActionMutation.isPending}
          >
            {performActionMutation.isPending ? 'Submitting...' : `Confirm ${actionType}`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Unmask Modal */}
      <UnmaskModal caseId={caseData.case_id} />
    </Box>
  );
};

export default CaseDetail;
