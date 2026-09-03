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
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Description as ReportIcon,
  Download as DownloadIcon,
  Add as AddIcon,
  PictureAsPdf as PdfIcon,
} from '@mui/icons-material';
import { officerService } from '../../../services/api';
import { OfficerReport } from '../../../types';
import { formatCurrency, formatDate } from '../../../utils/formatters';
import { toast } from 'react-hot-toast';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';

export const OfficerReports: React.FC = () => {
  const queryClient = useQueryClient();
  const [openModal, setOpenModal] = useState(false);
  const [reportTitle, setReportTitle] = useState('');
  const [reportPeriod, setReportPeriod] = useState('Q1 2024 (Jan - Mar)');

  const { data: reports, isLoading } = useQuery({
    queryKey: ['officer-reports'],
    queryFn: () => officerService.getReports(),
  });

  const generateMutation = useMutation({
    mutationFn: (data: { title: string; period: string }) =>
      officerService.generateReport(data),
    onSuccess: (newRep) => {
      queryClient.invalidateQueries({ queryKey: ['officer-reports'] });
      toast.success(`Executive Report "${newRep.title}" generated successfully!`);
      setOpenModal(false);
      setReportTitle('');
    },
  });

  const handleDownload = (rep: OfficerReport) => {
    toast.success(`Downloading PDF report for ${rep.title}...`);
  };

  const handleGenerate = () => {
    if (!reportTitle.trim()) {
      toast.error('Please enter a report title');
      return;
    }
    generateMutation.mutate({
      title: reportTitle,
      period: reportPeriod,
    });
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading executive audit reports archive..." />;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700}>
            Procurement Audit Reports & Executive Summaries
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Publishable statutory audit certifications, recovery statements, and department compliance scorecards.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenModal(true)}
        >
          Generate New Report
        </Button>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Report Title</TableCell>
              <TableCell>Audit Period</TableCell>
              <TableCell>Total Spend Scanned</TableCell>
              <TableCell>Flagged Risk Volume</TableCell>
              <TableCell>Compliance Score</TableCell>
              <TableCell>Publication Status</TableCell>
              <TableCell>Generated Date</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {reports?.map((rep) => (
              <TableRow key={rep.id} hover>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={1}>
                    <PdfIcon color="error" />
                    <Box>
                      <Typography variant="subtitle2" fontWeight={700}>
                        {rep.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {rep.summary}
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
                <TableCell>{rep.period}</TableCell>
                <TableCell>{formatCurrency(rep.total_spend)}</TableCell>
                <TableCell>
                  <Typography variant="body2" color="error.main" fontWeight={600}>
                    {formatCurrency(rep.flagged_spend)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={`${rep.compliance_score}%`}
                    color={rep.compliance_score > 90 ? 'success' : 'warning'}
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={rep.status.toUpperCase()}
                    color="primary"
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>{formatDate(rep.generated_at)}</TableCell>
                <TableCell align="center">
                  <Tooltip title="Download Signed PDF Report">
                    <IconButton color="primary" onClick={() => handleDownload(rep)}>
                      <DownloadIcon />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Generate Report Dialog */}
      <Dialog open={openModal} onClose={() => setOpenModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <ReportIcon color="primary" />
            <Typography variant="h6">Generate Executive Audit Report</Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Box display="flex" flexDirection="column" gap={2.5} my={1}>
            <TextField
              label="Report Title"
              fullWidth
              value={reportTitle}
              onChange={(e) => setReportTitle(e.target.value)}
              placeholder="e.g. FY24 Mid-Term Transportation Procurement Integrity Audit"
            />

            <FormControl fullWidth>
              <InputLabel>Audit Evaluation Period</InputLabel>
              <Select
                value={reportPeriod}
                label="Audit Evaluation Period"
                onChange={(e) => setReportPeriod(e.target.value)}
              >
                <MenuItem value="Q1 2024 (Jan - Mar)">Q1 2024 (Jan - Mar)</MenuItem>
                <MenuItem value="Q4 2023 (Oct - Dec)">Q4 2023 (Oct - Dec)</MenuItem>
                <MenuItem value="FY 2023 (Annual Review)">FY 2023 (Annual Review)</MenuItem>
                <MenuItem value="Year-to-Date (All Transactions)">Year-to-Date (All Transactions)</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setOpenModal(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleGenerate}
            disabled={generateMutation.isPending || !reportTitle.trim()}
          >
            {generateMutation.isPending ? 'Synthesizing...' : 'Generate & Compile PDF'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default OfficerReports;
