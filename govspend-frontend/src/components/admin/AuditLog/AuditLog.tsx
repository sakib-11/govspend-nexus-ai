import React, { useState } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  TextField,
  Grid,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  ReceiptLong as AuditIcon,
  Visibility as ViewIcon,
  FilterList as FilterIcon,
  Lock as LockIcon,
} from '@mui/icons-material';
import { adminService } from '../../../services/api';
import { AuditLogEntry } from '../../../types';
import { formatDate } from '../../../utils/formatters';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';

export const AuditLog: React.FC = () => {
  const [filterUser, setFilterUser] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [selectedEntry, setSelectedEntry] = useState<AuditLogEntry | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', filterUser, filterAction],
    queryFn: () =>
      adminService.getAuditLogs({
        userId: filterUser || undefined,
        action: filterAction || undefined,
      }),
  });

  if (isLoading) {
    return <LoadingSpinner message="Verifying tamper-evident cryptographic audit logs..." />;
  }

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700}>
          Immutable Hash-Chain Audit Log
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Cryptographically chained ledger recording all administrative, policy, unmasking, and case actions.
        </Typography>
      </Box>

      {/* Filter Bar */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4}>
            <TextField
              size="small"
              fullWidth
              label="Filter by User"
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              placeholder="e.g. carol, dave"
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              size="small"
              fullWidth
              label="Filter by Action"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              placeholder="e.g. UNMASK, POLICY, USER"
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <Box display="flex" gap={1}>
              <Button
                variant="outlined"
                startIcon={<FilterIcon />}
                onClick={() => refetch()}
              >
                Apply Filters
              </Button>
              <Button
                variant="text"
                onClick={() => {
                  setFilterUser('');
                  setFilterAction('');
                }}
              >
                Reset
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Audit Log Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Seq #</TableCell>
              <TableCell>Timestamp</TableCell>
              <TableCell>User</TableCell>
              <TableCell>Action</TableCell>
              <TableCell>Resource</TableCell>
              <TableCell>Hash Chain Digest (SHA-256)</TableCell>
              <TableCell align="center">Details</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.entries?.map((entry) => (
              <TableRow key={entry.entry_id} hover>
                <TableCell>
                  <Chip
                    label={`#${entry.hash_chain?.sequence || 1}`}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>{formatDate(entry.timestamp)}</TableCell>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {entry.user_id}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={entry.action}
                    size="small"
                    color={
                      entry.action.includes('UNMASK')
                        ? 'warning'
                        : entry.action.includes('POLICY')
                        ? 'info'
                        : 'default'
                    }
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {entry.resource_type}: {entry.resource_id || '—'}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={0.5}>
                    <LockIcon fontSize="small" sx={{ color: 'success.main', fontSize: 16 }} />
                    <Typography
                      variant="caption"
                      sx={{ fontFamily: 'monospace', color: 'text.secondary' }}
                    >
                      {entry.hash_chain?.hash?.substring(0, 16)}...
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="center">
                  <Tooltip title="View Payload & Verification">
                    <IconButton size="small" onClick={() => setSelectedEntry(entry)}>
                      <ViewIcon />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Entry Detail Dialog */}
      <Dialog
        open={Boolean(selectedEntry)}
        onClose={() => setSelectedEntry(null)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <AuditIcon color="primary" />
            <Typography variant="h6">Audit Record #{selectedEntry?.hash_chain?.sequence}</Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedEntry && (
            <Box display="flex" flexDirection="column" gap={2}>
              <Box>
                <Typography variant="caption" color="text.secondary">Entry ID</Typography>
                <Typography variant="body2" fontFamily="monospace">{selectedEntry.entry_id}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Action & Performer</Typography>
                <Typography variant="body2">{selectedEntry.action} by {selectedEntry.user_id}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Payload Details</Typography>
                <Paper sx={{ p: 1.5, bgcolor: 'action.hover', mt: 0.5 }}>
                  <Typography variant="caption" component="pre" sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', m: 0 }}>
                    {JSON.stringify(selectedEntry.details, null, 2)}
                  </Typography>
                </Paper>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Current Node Hash</Typography>
                <Typography variant="caption" display="block" fontFamily="monospace" color="success.main">
                  {selectedEntry.hash_chain?.hash}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Previous Node Hash (Chained)</Typography>
                <Typography variant="caption" display="block" fontFamily="monospace" color="text.secondary">
                  {selectedEntry.hash_chain?.previous_hash || 'Genesis (00000000000000000000000000000000)'}
                </Typography>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedEntry(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AuditLog;
