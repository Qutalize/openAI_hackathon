import { wsURL } from './api';
import type { ServerEvent } from '../types/protocol';

export class ControlSocket {
  socket?: WebSocket;
  closed = false;
  lastSeq = 0;
  private attempt = 0;
  private disconnectedAt = 0;
  private retryTimer?: ReturnType<typeof setTimeout>;
  private heartbeat?: ReturnType<typeof setInterval>;
  private pending = new Map<
    string,
    { resolve: (value: any) => void; reject: (reason: Error) => void; timer: ReturnType<typeof setTimeout> }
  >();
  constructor(
    private room: string,
    private onEvent: (e: ServerEvent) => void,
    private onState: (s: string) => void,
    private onOpen: () => Promise<void>,
    private heartbeatSeconds = 15,
    private reconnectSeconds = 60,
  ) {}

  connect() {
    if (this.closed) return;
    this.onState(this.attempt ? 'reconnecting' : 'connecting');
    const ws = (this.socket = new WebSocket(wsURL(`/ws/rooms/${encodeURIComponent(this.room)}`)));
    ws.onopen = async () => {
      if (this.closed) {
        ws.close();
        return;
      }
      this.heartbeat = setInterval(() => {
        this.request('ping', {}).catch(() => ws.close());
      }, this.heartbeatSeconds * 1000);
      try {
        await this.request('session.resume', { last_server_seq: this.lastSeq });
        await this.onOpen();
        this.attempt = 0;
        this.disconnectedAt = 0;
        this.onState('connected');
      } catch {
        ws.close();
      }
    };
    ws.onmessage = (message) => {
      let event: ServerEvent;
      try {
        event = JSON.parse(message.data);
      } catch {
        return;
      }
      const pending = event.request_id && this.pending.get(event.request_id);
      if (pending && ['ack', 'error', 'pong'].includes(event.type)) {
        clearTimeout(pending.timer);
        this.pending.delete(event.request_id!);
        if (event.type === 'error') pending.reject(new Error(event.payload.message));
        else pending.resolve(event.payload);
      }
      if (event.server_seq) this.lastSeq = Math.max(this.lastSeq, event.server_seq);
      this.onEvent(event);
    };
    ws.onclose = (event) => {
      clearInterval(this.heartbeat);
      for (const task of this.pending.values()) {
        clearTimeout(task.timer);
        task.reject(new Error('接続が切れました。再接続後に操作してください'));
      }
      this.pending.clear();
      if (this.closed) return;
      this.onState('reconnecting');
      if (!this.disconnectedAt) this.disconnectedAt = Date.now();
      if (
        [4401, 4403, 4001].includes(event.code) ||
        Date.now() - this.disconnectedAt > this.reconnectSeconds * 1000
      ) {
        this.onState('expired');
        return;
      }
      const delay = Math.min(1000 * 2 ** this.attempt++, 10000) + Math.random() * 300;
      this.retryTimer = setTimeout(() => this.connect(), delay);
    };
  }

  request<T = any>(type: string, payload: object): Promise<T> {
    if (this.socket?.readyState !== WebSocket.OPEN)
      return Promise.reject(new Error('接続の完了をお待ちください'));
    const request_id = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(request_id);
        reject(new Error('操作がタイムアウトしました'));
      }, 12000);
      this.pending.set(request_id, { resolve, reject, timer });
      this.socket!.send(JSON.stringify({ version: 1, type, request_id, payload }));
    });
  }

  close() {
    this.closed = true;
    clearTimeout(this.retryTimer);
    clearInterval(this.heartbeat);
    this.socket?.close();
    for (const p of this.pending.values()) {
      clearTimeout(p.timer);
      p.reject(new Error('会話を終了しました'));
    }
    this.pending.clear();
  }
}
