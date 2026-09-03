import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AppNotification } from '../../types';

interface UIState {
  sidebarOpen: boolean;
  theme: 'light' | 'dark';
  notificationDrawerOpen: boolean;
  notifications: AppNotification[];
  modals: {
    unmask: boolean;
    confirm: boolean;
    roleSwitcher: boolean;
    evidenceDetail: boolean;
  };
  modalData: any;

  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleTheme: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
  toggleNotificationDrawer: () => void;
  setNotificationDrawerOpen: (open: boolean) => void;
  addNotification: (notification: Omit<AppNotification, 'id' | 'timestamp' | 'read'>) => void;
  markNotificationAsRead: (id: string) => void;
  clearNotifications: () => void;
  openModal: (modal: keyof UIState['modals'], data?: any) => void;
  closeModal: (modal: keyof UIState['modals']) => void;
}

const initialNotifications: AppNotification[] = [
  {
    id: 'notif-1',
    title: 'High Risk Anomaly Detected',
    message: 'Case CS-849201 in Dept of Transportation has risk score 94%.',
    type: 'error',
    timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
    read: false,
    link: '/auditor/cases/cs-849201',
  },
  {
    id: 'notif-2',
    title: 'Dual-Control Unmask Requested',
    message: 'Auditor Carol requested unmasking for Vendor VK-83921.',
    type: 'warning',
    timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    read: false,
    link: '/auditor/cases/cs-849201',
  },
  {
    id: 'notif-3',
    title: 'Policy Weights Updated',
    message: 'Admin updated detector weights version to v2.1.',
    type: 'info',
    timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    read: true,
    link: '/admin/policies',
  },
];

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      theme: 'light',
      notificationDrawerOpen: false,
      notifications: initialNotifications,
      modals: {
        unmask: false,
        confirm: false,
        roleSwitcher: false,
        evidenceDetail: false,
      },
      modalData: null,

      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleTheme: () =>
        set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
      setTheme: (theme) => set({ theme }),
      toggleNotificationDrawer: () =>
        set((state) => ({ notificationDrawerOpen: !state.notificationDrawerOpen })),
      setNotificationDrawerOpen: (open) => set({ notificationDrawerOpen: open }),

      addNotification: (notif) =>
        set((state) => ({
          notifications: [
            {
              ...notif,
              id: `notif-${Date.now()}`,
              timestamp: new Date().toISOString(),
              read: false,
            },
            ...state.notifications,
          ],
        })),

      markNotificationAsRead: (id) =>
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        })),

      clearNotifications: () => set({ notifications: [] }),

      openModal: (modal, data = null) =>
        set((state) => ({
          modals: { ...state.modals, [modal]: true },
          modalData: data,
        })),

      closeModal: (modal) =>
        set((state) => ({
          modals: { ...state.modals, [modal]: false },
          modalData: null,
        })),
    }),
    {
      name: 'govspend-ui-storage',
      partialize: (state) => ({ theme: state.theme, sidebarOpen: state.sidebarOpen }),
    }
  )
);
