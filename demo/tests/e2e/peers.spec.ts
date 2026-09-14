import { expect, test } from '@playwright/test';
import { Peers, type RecoveryPolicy } from '../../frontend/src/services/peers';

class FakePeerConnection {
  connectionState: RTCPeerConnectionState = 'new';
  onconnectionstatechange: (() => void) | null = null;
  ontrack: RTCPeerConnection['ontrack'] = null;
  onicecandidate: RTCPeerConnection['onicecandidate'] = null;
  onnegotiationneeded: RTCPeerConnection['onnegotiationneeded'] = null;
  restartCount = 0;
  closed = false;

  constructor() {
    created.push(this);
  }

  addTransceiver() {
    return {} as RTCRtpTransceiver;
  }

  restartIce() {
    this.restartCount++;
  }

  close() {
    this.closed = true;
    this.connectionState = 'closed';
  }
}

let created: FakePeerConnection[];
const originalPeerConnection = globalThis.RTCPeerConnection;
const originalMediaStream = globalThis.MediaStream;
const policy: RecoveryPolicy = {
  disconnectedGraceMs: 30,
  failedGraceMs: 5,
  maxAttempts: 3,
  backoffBaseMs: 0,
};

test.beforeEach(() => {
  created = [];
  globalThis.RTCPeerConnection = FakePeerConnection as unknown as typeof RTCPeerConnection;
  globalThis.MediaStream = class {
    getTracks() {
      return [];
    }
  } as unknown as typeof MediaStream;
});

test.afterEach(() => {
  globalThis.RTCPeerConnection = originalPeerConnection;
  globalThis.MediaStream = originalMediaStream;
});

function setup() {
  const errors: string[] = [];
  const streams: Array<MediaStream | null> = [];
  const peers = new Peers(
    'a',
    {},
    async () => undefined,
    (_id, stream) => streams.push(stream),
    (message) => errors.push(message),
    new MediaStream(),
    policy,
  );
  return { errors, peers, streams };
}

test('failed connection restarts ICE and then replaces the peer', async () => {
  const { errors, peers, streams } = setup();
  const first = peers.ensure('b').pc as unknown as FakePeerConnection;

  first.connectionState = 'failed';
  first.onconnectionstatechange?.();

  expect(first.restartCount).toBe(1);
  await new Promise((resolve) => setTimeout(resolve, 30));
  expect(first.closed).toBe(true);
  expect(created).toHaveLength(2);
  expect(streams).toEqual([null]);
  expect(errors).toContain('映像・音声の再接続を試みています。字幕は利用できます');
  expect(errors.some((message) => message.includes('接続を再作成しています'))).toBe(true);
  peers.close();
});

test('recovery attempts stop at the configured limit', async () => {
  const { errors, peers } = setup();
  peers.ensure('b');

  for (let attempt = 0; attempt < policy.maxAttempts + 1; attempt++) {
    const current = peers.peers.get('b')!.pc as unknown as FakePeerConnection;
    current.connectionState = 'failed';
    current.onconnectionstatechange?.();
    await new Promise((resolve) => setTimeout(resolve, 15));
  }

  expect(created).toHaveLength(policy.maxAttempts + 1);
  expect(errors.filter((message) => message.includes('再入室してください'))).toHaveLength(1);
  peers.close();
});

test('temporary disconnection does not replace a peer that reconnects within the grace period', async () => {
  const { peers } = setup();
  const first = peers.ensure('b').pc as unknown as FakePeerConnection;

  first.connectionState = 'disconnected';
  first.onconnectionstatechange?.();
  await new Promise((resolve) => setTimeout(resolve, 10));
  first.connectionState = 'connected';
  first.onconnectionstatechange?.();
  await new Promise((resolve) => setTimeout(resolve, 50));

  expect(first.closed).toBe(false);
  expect(created).toHaveLength(1);
  peers.close();
});
