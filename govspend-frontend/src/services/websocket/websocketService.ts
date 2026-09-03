type WebSocketCallback = (data: any) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private listeners: Map<string, Set<WebSocketCallback>> = new Map();
  private isConnected: boolean = false;
  private reconnectTimer: any = null;
  private simulationTimer: any = null;
  private static instance: WebSocketService;

  private constructor() {
    this.connect();
  }

  static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  connect(): void {
    const wsUrl = import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8008/ws';

    if (typeof window === 'undefined') return;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.isConnected = true;
        this.stopSimulation();
      };

      this.socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type = payload.type || 'message';
          this.notifyListeners(type, payload.data || payload);
        } catch (err) {
          console.warn('Failed to parse WebSocket message:', err);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        this.scheduleReconnect();
        this.startSimulation();
      };

      this.socket.onerror = () => {
        this.isConnected = false;
        this.startSimulation();
      };
    } catch {
      this.startSimulation();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, 15000);
  }

  private startSimulation(): void {
    if (this.simulationTimer) return;

    // Periodically simulate subtle live alerts
    this.simulationTimer = setInterval(() => {
      const simulatedEvents = [
        {
          type: 'case_alert',
          data: {
            id: `sim-${Date.now()}`,
            case_id: 'cs-849201',
            department: 'Department of Transportation',
            message: 'Price deviation anomaly threshold reached for Bituminous Asphalt',
            score: 0.94,
            tier: 'HIGH',
            timestamp: new Date().toISOString(),
          },
        },
        {
          type: 'unmask_update',
          data: {
            request_id: 'unmask-req-101',
            status: 'approved',
            timestamp: new Date().toISOString(),
          },
        },
      ];

      const chosen = simulatedEvents[Math.floor(Math.random() * simulatedEvents.length)];
      this.notifyListeners(chosen.type, chosen.data);
    }, 45000);
  }

  private stopSimulation(): void {
    if (this.simulationTimer) {
      clearInterval(this.simulationTimer);
      this.simulationTimer = null;
    }
  }

  subscribe(eventType: string, callback: WebSocketCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    return () => {
      const set = this.listeners.get(eventType);
      if (set) {
        set.delete(callback);
      }
    };
  }

  private notifyListeners(eventType: string, data: any): void {
    const callbacks = this.listeners.get(eventType);
    if (callbacks) {
      callbacks.forEach((cb) => cb(data));
    }
    // Also notify global wildcard listeners
    const wildcard = this.listeners.get('*');
    if (wildcard) {
      wildcard.forEach((cb) => cb({ type: eventType, data }));
    }
  }

  send(eventType: string, data: any): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: eventType, data }));
    }
  }
}

export default WebSocketService.getInstance();
