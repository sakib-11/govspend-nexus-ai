import { useEffect } from 'react';
import websocketService from '../services/websocket/websocketService';
import { useUIStore } from '../store';
import { toast } from 'react-hot-toast';

export function useLiveAlerts() {
  const { addNotification } = useUIStore();

  useEffect(() => {
    const unsubCase = websocketService.subscribe('case_alert', (data) => {
      addNotification({
        title: `Live Alert: ${data.department}`,
        message: data.message,
        type: data.tier === 'HIGH' ? 'error' : 'warning',
        link: `/auditor/cases/${data.case_id}`,
      });
      toast(`⚠️ Anomaly: ${data.message}`, {
        duration: 5000,
      });
    });

    const unsubUnmask = websocketService.subscribe('unmask_update', (data) => {
      addNotification({
        title: 'Unmask Request Approved',
        message: `Request ${data.request_id} has been approved by the Checker.`,
        type: 'info',
        link: '/auditor/cases',
      });
    });

    return () => {
      unsubCase();
      unsubUnmask();
    };
  }, [addNotification]);
}
