import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../../store';
import { UserRole } from '../../../types';

interface ProtectedRouteProps {
  allowedRoles?: UserRole[] | string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles }) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const hasRole = user.roles.some((r) =>
      allowedRoles.some((ar) => ar === r || (typeof ar === 'string' && r.includes(ar)))
    );
    if (!hasRole) {
      // If user doesn't have the role, redirect to appropriate role home
      if (user.roles.some((r) => r.includes('admin'))) {
        return <Navigate to="/admin/dashboard" replace />;
      }
      if (user.roles.includes(UserRole.OFFICER)) {
        return <Navigate to="/officer/dashboard" replace />;
      }
      return <Navigate to="/auditor/cases" replace />;
    }
  }

  return <Outlet />;
};

export default ProtectedRoute;
