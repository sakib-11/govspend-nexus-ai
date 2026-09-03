import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Chip,
  Typography,
  Box,
} from '@mui/material';
import {
  AdminPanelSettings as AdminIcon,
  Security as SuperAdminIcon,
  AssignmentTurnedIn as Auditor3Icon,
  Assessment as Auditor2Icon,
  Person as Auditor1Icon,
  Person as PersonIcon,
  AccountBalance as OfficerIcon,
  CheckCircle as ActiveIcon,
} from '@mui/icons-material';
import { useAuthStore, useUIStore } from '../../../store';
import { DEMO_USERS } from '../../../store/slices/authSlice';
import { toast } from 'react-hot-toast';

export const RoleSwitcherModal: React.FC = () => {
  const navigate = useNavigate();
  const { user, loginAsDemoUser } = useAuthStore();
  const { modals, closeModal } = useUIStore();

  const handleSelectRole = (roleKey: string) => {
    loginAsDemoUser(roleKey as any);
    closeModal('roleSwitcher');
    toast.success(`Switched role to: ${DEMO_USERS[roleKey]?.full_name}`);

    // Navigate to appropriate default view
    if (roleKey.includes('admin')) {
      navigate('/admin/dashboard');
    } else if (roleKey === 'officer') {
      navigate('/officer/dashboard');
    } else {
      navigate('/auditor/cases');
    }
  };

  const getRoleIcon = (key: string) => {
    switch (key) {
      case 'super_admin':
        return <SuperAdminIcon color="error" />;
      case 'admin':
        return <AdminIcon color="primary" />;
      case 'auditor_l3':
        return <Auditor3Icon color="success" />;
      case 'auditor_l2':
        return <Auditor2Icon color="secondary" />;
      case 'auditor_l1':
        return <Auditor1Icon color="info" />;
      case 'officer':
        return <OfficerIcon color="warning" />;
      default:
        return <PersonIcon />;
    }
  };

  return (
    <Dialog
      open={modals.roleSwitcher}
      onClose={() => closeModal('roleSwitcher')}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        <Typography variant="h6" component="div">
          Persona Switcher (Demo / Dual-Control)
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Select any persona to test role-based access control, maker-checker unmasking, and dashboards.
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ p: 0 }}>
        <List>
          {Object.entries(DEMO_USERS).map(([key, demoUser]) => {
            const isCurrent = user?.user_id === demoUser.user_id;
            return (
              <ListItem key={key} disablePadding divider>
                <ListItemButton
                  selected={isCurrent}
                  onClick={() => handleSelectRole(key)}
                  sx={{ py: 1.5, px: 3 }}
                >
                  <ListItemIcon>{getRoleIcon(key)}</ListItemIcon>
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2" fontWeight={700}>
                          {demoUser.full_name}
                        </Typography>
                        {isCurrent && (
                          <Chip
                            label="Active"
                            size="small"
                            color="success"
                            icon={<ActiveIcon />}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box mt={0.5}>
                        <Typography variant="caption" color="text.secondary" display="block">
                          Jurisdictions: {demoUser.jurisdictions.join(', ')}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Roles: {demoUser.roles.join(', ')}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={() => closeModal('roleSwitcher')}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default RoleSwitcherModal;
