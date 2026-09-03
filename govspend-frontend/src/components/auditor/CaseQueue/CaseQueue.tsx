import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Typography,
  Button,
  Tooltip,
  InputAdornment,
  ButtonGroup,
} from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import {
  Refresh as RefreshIcon,
  FilterList as FilterIcon,
  Visibility as ViewIcon,
  Search as SearchIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { caseService } from '../../../services/api';
import { useCaseStore } from '../../../store';
import { Case } from '../../../types';
import {
  formatCurrency,
  formatRiskScore,
  getTierColor,
  getStatusColor,
} from '../../../utils/formatters';
import TableSkeleton from '../../common/Loading/TableSkeleton';

export const CaseQueue: React.FC = () => {
  const navigate = useNavigate();
  const { filters, pagination, setFilters, resetFilters, setPagination } = useCaseStore();
  const [filterOpen, setFilterOpen] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['cases', filters, pagination.page, pagination.limit],
    queryFn: () =>
      caseService.getCases({
        ...filters,
        page: pagination.page,
        limit: pagination.limit,
      }),
  });

  const handlePreset = (preset: 'all' | 'high' | 'review') => {
    if (preset === 'all') {
      resetFilters();
    } else if (preset === 'high') {
      setFilters({ tiers: ['HIGH'], statuses: [] });
    } else if (preset === 'review') {
      setFilters({ statuses: ['NEW', 'UNDER_REVIEW'], tiers: [] });
    }
  };

  return (
    <Box>
      {/* Header Bar */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Procurement Case Audit Queue
          </Typography>
          <Typography variant="body2" color="text.secondary">
            AI-flagged procurement transactions prioritized by ensemble risk score and anomaly severity.
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Refresh Cases">
            <IconButton onClick={() => refetch()} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button
            variant={filterOpen ? 'contained' : 'outlined'}
            startIcon={<FilterIcon />}
            onClick={() => setFilterOpen(!filterOpen)}
          >
            Filters
          </Button>
        </Box>
      </Box>

      {/* Preset Quick Filters */}
      <Box display="flex" gap={1} mb={2} alignItems="center">
        <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mr: 1 }}>
          PRESETS:
        </Typography>
        <ButtonGroup size="small" variant="outlined">
          <Button onClick={() => handlePreset('all')}>All Cases</Button>
          <Button onClick={() => handlePreset('review')} color="warning">
            Pending Review
          </Button>
          <Button onClick={() => handlePreset('high')} color="error">
            High Risk Only
          </Button>
        </ButtonGroup>
      </Box>

      {/* Expanded Filter Panel */}
      {filterOpen && (
        <Paper sx={{ p: 2.5, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Risk Tier</InputLabel>
                <Select
                  multiple
                  value={filters.tiers || []}
                  onChange={(e) =>
                    setFilters({
                      tiers:
                        typeof e.target.value === 'string'
                          ? [e.target.value]
                          : e.target.value,
                    })
                  }
                  label="Risk Tier"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((val) => (
                        <Chip key={val} label={val} size="small" color={getTierColor(val)} />
                      ))}
                    </Box>
                  )}
                >
                  <MenuItem value="HIGH">High Risk</MenuItem>
                  <MenuItem value="BORDERLINE">Borderline</MenuItem>
                  <MenuItem value="LOW">Low Risk</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Audit Status</InputLabel>
                <Select
                  multiple
                  value={filters.statuses || []}
                  onChange={(e) =>
                    setFilters({
                      statuses:
                        typeof e.target.value === 'string'
                          ? [e.target.value]
                          : e.target.value,
                    })
                  }
                  label="Audit Status"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((val) => (
                        <Chip key={val} label={val} size="small" color={getStatusColor(val)} />
                      ))}
                    </Box>
                  )}
                >
                  <MenuItem value="NEW">New</MenuItem>
                  <MenuItem value="UNDER_REVIEW">Under Review</MenuItem>
                  <MenuItem value="APPROVED">Approved</MenuItem>
                  <MenuItem value="REJECTED">Rejected</MenuItem>
                  <MenuItem value="ESCALATED">Escalated</MenuItem>
                  <MenuItem value="CLOSED">Closed</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Department"
                value={filters.department || ''}
                onChange={(e) => setFilters({ department: e.target.value })}
                placeholder="e.g. Transportation"
              />
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                size="small"
                label="Search Keyword / ID"
                value={filters.search || ''}
                onChange={(e) => setFilters({ search: e.target.value })}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>

            <Grid item xs={12} display="flex" justifyContent="flex-end">
              <Button
                variant="outlined"
                color="secondary"
                startIcon={<ClearIcon />}
                onClick={resetFilters}
              >
                Clear All Filters
              </Button>
            </Grid>
          </Grid>
        </Paper>
      )}

      {/* Main Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Case ID</TableCell>
              <TableCell>Department</TableCell>
              <TableCell>Risk Score</TableCell>
              <TableCell>Tier</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Billed Amount</TableCell>
              <TableCell>Top Flagged Signals</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableSkeleton columns={8} rows={6} />
            ) : !data?.cases || data.cases.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ py: 6 }}>
                  <Typography color="text.secondary">No cases matching current criteria.</Typography>
                </TableCell>
              </TableRow>
            ) : (
              data.cases.map((item: Case) => (
                <TableRow key={item.case_id} hover sx={{ cursor: 'pointer' }}>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Typography variant="subtitle2" fontWeight={700} color="primary.main">
                      {item.case_id.toUpperCase()}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Tx: {item.transaction_id}
                    </Typography>
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Typography variant="body2">{item.department}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Vendor: {item.vendor_token}
                    </Typography>
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Chip
                      label={formatRiskScore(item.risk_score)}
                      color={getTierColor(item.tier)}
                      size="small"
                      sx={{ fontWeight: 700 }}
                    />
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Chip
                      label={item.tier}
                      color={getTierColor(item.tier)}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Chip
                      label={item.status.replace(/_/g, ' ')}
                      color={getStatusColor(item.status)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Typography variant="body2" fontWeight={600}>
                      {formatCurrency(item.amount)}
                    </Typography>
                  </TableCell>
                  <TableCell onClick={() => navigate(`/auditor/cases/${item.case_id}`)}>
                    <Box display="flex" flexWrap="wrap" gap={0.5}>
                      {item.top_signals?.slice(0, 2).map((sig, idx) => (
                        <Chip
                          key={idx}
                          label={`${sig.detector_type.replace(/_/g, ' ')} (${(sig.signal_value * 100).toFixed(0)}%)`}
                          size="small"
                          sx={{ fontSize: '0.7rem' }}
                        />
                      ))}
                      {(item.signal_count || item.top_signals?.length) > 2 && (
                        <Chip
                          label={`+${(item.signal_count || item.top_signals.length) - 2}`}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Inspect Case Details & Evidence">
                      <IconButton
                        color="primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/auditor/cases/${item.case_id}`);
                        }}
                      >
                        <ViewIcon />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25, 50]}
          component="div"
          count={data?.total || 0}
          rowsPerPage={pagination.limit}
          page={pagination.page - 1}
          onPageChange={(_, newPage) =>
            setPagination({ ...pagination, page: newPage + 1 })
          }
          onRowsPerPageChange={(e) =>
            setPagination({
              ...pagination,
              limit: parseInt(e.target.value, 10),
              page: 1,
            })
          }
        />
      </TableContainer>
    </Box>
  );
};

export default CaseQueue;
