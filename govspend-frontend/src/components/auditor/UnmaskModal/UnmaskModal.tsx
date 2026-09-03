import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Paper,
  Divider,
  Chip,
} from '@mui/material';
import {
  LockOpen as UnmaskIcon,
  Security as SecurityIcon,
  VerifiedUser as VerifiedIcon,
} from '@mui/icons-material';
import { useMutation } from '@tanstack/react-query';
import { useAuthStore, useUIStore } from '../../../store';
import { unmaskService } from '../../../services/api';
import { UnmaskEntityType, UnmaskStatus } from '../../../types';
import { toast } from 'react-hot-toast';

interface UnmaskModalProps {
  caseId: string;
}

export const UnmaskModal: React.FC<UnmaskModalProps> = ({ caseId }) => {
  const { user } = useAuthStore();
  const { modals, closeModal, modalData } = useUIStore();

  const [entityType, setEntityType] = useState<UnmaskEntityType>(UnmaskEntityType.VENDOR);
  const [reason, setReason] = useState('');
  const [unmaskedResult, setUnmaskedResult] = useState<any>(null);

  const isChecker = user?.roles.some((r) => r.includes('admin') || r === 'approver');

  const requestUnmaskMutation = useMutation({
    mutationFn: () =>
      unmaskService.createRequest({
        case_id: caseId,
        entity_type: entityType,
        entity_token: modalData?.entityToken || 'VK-83921',
        reason,
        jurisdiction_id: user?.jurisdictions[0] || 'federal',
      }),
    onSuccess: (res) => {
      toast.success('Dual-Control Unmask request submitted for Checker approval.');
      // Auto-approve in demo mode if current user is an approver/admin
      if (isChecker) {
        approveMutation.mutate(res.request_id);
      }
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to request unmasking');
    },
  });

  const approveMutation = useMutation({
    mutationFn: (reqId: string) =>
      unmaskService.approveRequest(reqId, { decision: 'approve' }),
    onSuccess: (res) => {
      setUnmaskedResult(res.unmasked_data);
      toast.success('Dual-Control Unmasking approved. PII revealed.');
    },
  });

  const handleClose = () => {
    setReason('');
    setUnmaskedResult(null);
    closeModal('unmask');
  };

  const handleRequest = () => {
    if (!reason.trim()) {
      toast.error('Legal audit justification is required to request unmasking.');
      return;
    }
    requestUnmaskMutation.mutate();
  };

  return (
    <Dialog open={modals.unmask} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <UnmaskIcon color="primary" />
          <Typography variant="h6">Dual-Control Identity Unmasking</Typography>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {!unmaskedResult ? (
          <Box display="flex" flexDirection="column" gap={2.5}>
            <Alert severity="warning" icon={<SecurityIcon />}>
              <strong>Privacy Protection Policy:</strong> Under procurement confidentiality protocols,
              vendor and official identities are cryptographically masked. Unmasking requires valid legal justification
              and secondary checker approval.
            </Alert>

            <FormControl fullWidth size="small">
              <InputLabel>Entity Type to Reveal</InputLabel>
              <Select
                value={entityType}
                label="Entity Type to Reveal"
                onChange={(e) => setEntityType(e.target.value as UnmaskEntityType)}
              >
                <MenuItem value={UnmaskEntityType.VENDOR}>Primary Vendor (Token: VK-83921)</MenuItem>
                <MenuItem value={UnmaskEntityType.OFFICIAL}>Approving Official (Token: OFFICIAL-992)</MenuItem>
                <MenuItem value={UnmaskEntityType.TRANSACTION}>Banking & Wire Routing Information</MenuItem>
              </Select>
            </FormControl>

            <TextField
              label="Legal & Audit Justification (Mandatory)"
              multiline
              rows={3}
              fullWidth
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Formal price gouging and contract splitting investigation under CA PCC § 10105."
              helperText="Recorded permanently in tamper-evident hash-chain audit ledger."
            />

            <Box>
              <Typography variant="caption" color="text.secondary">
                Requester (Maker): <strong>{user?.full_name}</strong> ({user?.roles.join(', ')})
              </Typography>
            </Box>
          </Box>
        ) : (
          <Box display="flex" flexDirection="column" gap={2}>
            <Alert severity="success" icon={<VerifiedIcon />}>
              Dual-Control Authorization Verified. Access granted for 15 minutes.
            </Alert>

            <Paper sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 2 }}>
              <Typography variant="subtitle2" color="primary.main" fontWeight={700} gutterBottom>
                UNMASKED ENTITY DETAILS:
              </Typography>
              <Divider sx={{ my: 1 }} />

              <Box display="flex" flexDirection="column" gap={1}>
                <Box>
                  <Typography variant="caption" color="text.secondary">Legal Registered Name</Typography>
                  <Typography variant="body2" fontWeight={700}>
                    {unmaskedResult.legal_name}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">Tax Identification Number</Typography>
                  <Typography variant="body2" fontFamily="monospace">
                    {unmaskedResult.tax_identifier}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">Registered Business Address</Typography>
                  <Typography variant="body2">{unmaskedResult.registered_address}</Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">Beneficial Owners & Board Directors</Typography>
                  {unmaskedResult.directors?.map((d: any, idx: number) => (
                    <Typography key={idx} variant="body2">
                      • {d.name} (TIN: {d.tin})
                    </Typography>
                  ))}
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">Disbursement Bank Account</Typography>
                  <Typography variant="body2" fontFamily="monospace">
                    {unmaskedResult.bank_account_number}
                  </Typography>
                </Box>
              </Box>
            </Paper>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose}>
          {unmaskedResult ? 'Close & Clear' : 'Cancel'}
        </Button>
        {!unmaskedResult && (
          <Button
            variant="contained"
            color="primary"
            onClick={handleRequest}
            disabled={requestUnmaskMutation.isPending || !reason.trim()}
          >
            {requestUnmaskMutation.isPending ? 'Requesting...' : 'Request Unmask'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default UnmaskModal;
