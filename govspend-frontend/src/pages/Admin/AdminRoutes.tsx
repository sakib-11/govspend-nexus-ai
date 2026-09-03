import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '../../store';
import AdminDashboard from '../../components/admin/Dashboard/AdminDashboard';
import PolicyManagement from '../../components/admin/PolicyManagement/PolicyManagement';
import UserManagement from '../../components/admin/UserManagement/UserManagement';
import AuditLog from '../../components/admin/AuditLog/AuditLog';
import AdminMetrics from '../../components/admin/Metrics/AdminMetrics';

export const AdminRoutes: React.FC = () => {
  const { user } = useAuthStore();

  if (!user?.roles.some((r) => r === 'admin' || r === 'super_admin')) {
    return <Navigate to="/auditor/cases" replace />;
  }

  return (
    <Routes>
      <Route index element={<Navigate to="dashboard" replace />} />
      <Route path="dashboard" element={<AdminDashboard />} />
      <Route path="policies" element={<PolicyManagement />} />
      <Route path="users" element={<UserManagement />} />
      <Route path="audit" element={<AuditLog />} />
      <Route path="metrics" element={<AdminMetrics />} />
    </Routes>
  );
};

export default AdminRoutes;
