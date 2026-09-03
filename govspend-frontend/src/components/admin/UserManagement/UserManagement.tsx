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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  ListItemText,
} from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Edit as EditIcon, Security as SecurityIcon } from '@mui/icons-material';
import { adminService } from '../../../services/api';
import { User, UserRole } from '../../../types';
import { toast } from 'react-hot-toast';
import LoadingSpinner from '../../common/Loading/LoadingSpinner';

const AVAILABLE_ROLES = [
  UserRole.SUPER_ADMIN,
  UserRole.ADMIN,
  UserRole.AUDITOR_LEVEL_3,
  UserRole.AUDITOR_LEVEL_2,
  UserRole.AUDITOR_LEVEL_1,
  UserRole.OFFICER,
  UserRole.APPROVER,
  UserRole.REVIEWER,
  UserRole.DATA_ANALYST,
  UserRole.READ_ONLY,
];

const AVAILABLE_JURISDICTIONS = [
  'federal',
  'state-california',
  'state-new-york',
  'state-texas',
  'local-nyc',
  'local-la',
];

export const UserManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [editRoles, setEditRoles] = useState<string[]>([]);
  const [editJurisdictions, setEditJurisdictions] = useState<string[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: users, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => adminService.listUsers(),
  });

  const updateUserMutation = useMutation({
    mutationFn: (data: { userId: string; roles: string[]; jurisdictions: string[] }) =>
      adminService.updateUserRoles(data.userId, {
        user_id: data.userId,
        roles: data.roles,
        jurisdictions: data.jurisdictions,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      toast.success('User roles and jurisdictions updated successfully');
      setDialogOpen(false);
    },
    onError: (err: any) => {
      toast.error(err.message || 'Failed to update user roles');
    },
  });

  const handleOpenEdit = (user: User) => {
    setSelectedUser(user);
    setEditRoles(user.roles || []);
    setEditJurisdictions(user.jurisdictions || []);
    setDialogOpen(true);
  };

  const handleSave = () => {
    if (!selectedUser) return;
    updateUserMutation.mutate({
      userId: selectedUser.user_id,
      roles: editRoles,
      jurisdictions: editJurisdictions,
    });
  };

  if (isLoading) {
    return <LoadingSpinner message="Loading user authorization catalog..." />;
  }

  return (
    <Box>
      <Box mb={3}>
        <Typography variant="h4" fontWeight={700}>
          User Access & Jurisdiction Enforcement
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage role-based access control (RBAC), approval limits, and multi-tenant jurisdiction boundaries.
        </Typography>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>User ID</TableCell>
              <TableCell>Full Name</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Assigned Roles</TableCell>
              <TableCell>Jurisdictions Enforced</TableCell>
              <TableCell>MFA</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users?.map((user) => (
              <TableRow key={user.user_id} hover>
                <TableCell>
                  <Typography variant="subtitle2" fontWeight={700}>
                    {user.user_id}
                  </Typography>
                </TableCell>
                <TableCell>{user.full_name}</TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>
                  <Box display="flex" flexWrap="wrap" gap={0.5}>
                    {user.roles.map((r) => (
                      <Chip
                        key={r}
                        label={r}
                        size="small"
                        color={
                          r.includes('admin')
                            ? 'error'
                            : r.includes('auditor')
                            ? 'primary'
                            : 'warning'
                        }
                      />
                    ))}
                  </Box>
                </TableCell>
                <TableCell>
                  <Box display="flex" flexWrap="wrap" gap={0.5}>
                    {user.jurisdictions.map((j) => (
                      <Chip key={j} label={j} size="small" variant="outlined" />
                    ))}
                  </Box>
                </TableCell>
                <TableCell>
                  <Chip
                    label={user.mfa_enabled ? 'Enabled' : 'Disabled'}
                    size="small"
                    color={user.mfa_enabled ? 'success' : 'default'}
                  />
                </TableCell>
                <TableCell align="center">
                  <Tooltip title="Modify Roles & Jurisdiction">
                    <IconButton size="small" onClick={() => handleOpenEdit(user)}>
                      <EditIcon />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Edit User Modal */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <SecurityIcon color="primary" />
            <Typography variant="h6">Edit User Roles & Jurisdictions</Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          {selectedUser && (
            <Box display="flex" flexDirection="column" gap={3} my={1}>
              <Typography variant="subtitle2">
                User: <strong>{selectedUser.full_name}</strong> ({selectedUser.email})
              </Typography>

              <FormControl fullWidth>
                <InputLabel>Assigned Roles</InputLabel>
                <Select
                  multiple
                  value={editRoles}
                  onChange={(e) =>
                    setEditRoles(
                      typeof e.target.value === 'string'
                        ? e.target.value.split(',')
                        : e.target.value
                    )
                  }
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  {AVAILABLE_ROLES.map((role) => (
                    <MenuItem key={role} value={role}>
                      <Checkbox checked={editRoles.indexOf(role) > -1} />
                      <ListItemText primary={role} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl fullWidth>
                <InputLabel>Allowed Jurisdictions</InputLabel>
                <Select
                  multiple
                  value={editJurisdictions}
                  onChange={(e) =>
                    setEditJurisdictions(
                      typeof e.target.value === 'string'
                        ? e.target.value.split(',')
                        : e.target.value
                    )
                  }
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((value) => (
                        <Chip key={value} label={value} size="small" variant="outlined" />
                      ))}
                    </Box>
                  )}
                >
                  {AVAILABLE_JURISDICTIONS.map((jur) => (
                    <MenuItem key={jur} value={jur}>
                      <Checkbox checked={editJurisdictions.indexOf(jur) > -1} />
                      <ListItemText primary={jur} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={updateUserMutation.isPending}
          >
            {updateUserMutation.isPending ? 'Saving...' : 'Save Permissions'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UserManagement;
