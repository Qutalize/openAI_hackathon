import { wsURL } from './api';
import type { StreamInfo } from '../types/protocol';

export class MediaSocket {
  socket?: WebSocket;
  seq = -1;
  stream?: StreamInfo;
  private closed = false;
  constructor(
    private room: string,
    private onClose: () => void,
  ) {}
  async connect() {
    this.closed = false;
    return new Promise<void>((resolve, reject) => {
      const ws = (this.socket = new WebSocket(wsURL(`/ws/rooms/${encodeURIComponent(this.room)}/media`)));
      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error('認識接続を開始できません'));
      ws.onclose = () => {
        if (!this.closed) this.onClose();
      };
    });
  }
  reset(stream: StreamInfo) {
    this.stream = stream;
    this.seq = -1;
  }
  send(kind: string, body: ArrayBuffer, extra: object = {}, capture = performance.now()) {
    if (!this.stream || this.socket?.readyState !== WebSocket.OPEN) return false;
    if (this.socket.bufferedAmount > 32000)
      throw new Error('認識接続が混雑しています。区間をやり直してください');
    const header = new TextEncoder().encode(
      JSON.stringify({ version: 1, kind, ...this.stream, seq: ++this.seq, capture_ms: capture, ...extra }),
    );
    const packet = new Uint8Array(4 + header.length + body.byteLength);
    new DataView(packet.buffer).setUint32(0, header.length, true);
    packet.set(header, 4);
    packet.set(new Uint8Array(body), 4 + header.length);
    this.socket.send(packet);
    return true;
  }
  close() {
    this.closed = true;
    this.socket?.close();
    this.socket = undefined;
  }
}
