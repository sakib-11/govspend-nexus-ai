import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import OfficerDashboard from '../../components/officer/Dashboard/OfficerDashboard';
import OfficerReports from '../../components/officer/Reports/OfficerReports';
import OfficerAnalytics from '../../components/officer/Analytics/OfficerAnalytics';
import InstitutionPortal from './InstitutionPortal';

export const OfficerRoutes: React.FC = () => {
  return (
    <Routes>
      <Route index element={<Navigate to="dashboard" replace />} />
      <Route path="dashboard" element={<OfficerDashboard />} />
      <Route path="reports" element={<OfficerReports />} />
      <Route path="analytics" element={<OfficerAnalytics />} />
      <Route path="compliance" element={<OfficerDashboard />} />
      <Route path="institution" element={<InstitutionPortal />} />
    </Routes>
  );
};

export default OfficerRoutes;
