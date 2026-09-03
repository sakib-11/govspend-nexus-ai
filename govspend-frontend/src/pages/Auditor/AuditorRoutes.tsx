import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import CaseQueue from '../../components/auditor/CaseQueue/CaseQueue';
import CaseDetail from '../../components/auditor/CaseDetail/CaseDetail';
import VendorGraph from '../../components/auditor/VendorGraph/VendorGraph';
import { Box, Typography, Paper } from '@mui/material';

export const AuditorRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<Navigate to="cases" replace />} />
      <Route path="cases" element={<CaseQueue />} />
      <Route path="cases/:caseId" element={<CaseDetail />} />
      <Route path="my-cases" element={<CaseQueue />} />
      <Route
        path="analytics"
        element={
          <Box>
            <Typography variant="h4" fontWeight={700} mb={1}>
              Vendor Corporate Linkage & Network Analysis
            </Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>
              Deep investigation of vendor corporate graph relationships, shared shell companies, and conflict-of-interest linkages.
            </Typography>
            <Paper sx={{ p: 3 }}>
              <VendorGraph vendorToken="VK-83921" />
            </Paper>
          </Box>
        }
      />
    </Routes>
  );
};

export default AuditorRoutes;
