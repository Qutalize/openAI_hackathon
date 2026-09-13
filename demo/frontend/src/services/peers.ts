interface Peer {
  pc: RTCPeerConnection;
  makingOffer: boolean;
  ignoreOffer: boolean;
  settingAnswer: boolean;
  candidates: RTCIceCandidateInit[];
}

export class Peers {
  peers = new Map<string, Peer>();
  closed = false;
  constructor(
    private self: string,
    private config: RTCConfiguration,
    private signal: (type: string, payload: any) => Promise<unknown>,
    private onStream: (id: string, stream: MediaStream | null) => void,
    private onError: (message: string) => void,
    private local: MediaStream,
  ) {}

  ensure(id: string) {
    if (this.peers.has(id)) return this.peers.get(id)!;
    const pc = new RTCPeerConnection(this.config);
    const peer: Peer = { pc, makingOffer: false, ignoreOffer: false, settingAnswer: false, candidates: [] };
    this.peers.set(id, peer);
    // Only the initial offerer creates m-lines. The answerer reuses the offered
    // transceivers; preallocating on both sides creates duplicate send-only tracks.
    if (this.self < id)
      for (const kind of ['audio', 'video']) {
        const track = this.local.getTracks().find((t) => t.kind === kind);
        pc.addTransceiver(track ?? kind, { direction: 'sendrecv', streams: [this.local] });
      }
    pc.ontrack = (event) => {
      const stream = event.streams[0] ?? new MediaStream(pc.getReceivers().map((r) => r.track));
      this.onStream(id, stream);
    };
    pc.onicecandidate = (event) => {
      if (event.candidate)
        this.signal('rtc.ice', { target_id: id, candidate: event.candidate.toJSON() }).catch(() => {});
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed') {
        this.onError('映像・音声の再接続を試みています。字幕は利用できます');
        pc.restartIce();
      }
    };
    pc.onnegotiationneeded = async () => {
      // Initial offer has one owner; later negotiations use the polite-peer algorithm.
      if (!pc.remoteDescription && this.self > id) return;
      try {
        peer.makingOffer = true;
        await pc.setLocalDescription();
        await this.signal(`rtc.${pc.localDescription!.type}`, {
          target_id: id,
          description: pc.localDescription!.toJSON(),
        });
      } catch {
        if (!this.closed) this.onError('映像接続を確立できませんでした');
      } finally {
        peer.makingOffer = false;
      }
    };
    return peer;
  }

  async receive(type: string, payload: any) {
    if (this.closed) return;
    const id = payload.from_id;
    if (!id || id === this.self) return;
    const peer = this.ensure(id),
      pc = peer.pc;
    try {
      if (type === 'rtc.ice') {
        if (!pc.remoteDescription) peer.candidates.push(payload.candidate);
        else if (!peer.ignoreOffer) await pc.addIceCandidate(payload.candidate);
      } else {
        const description = payload.description as RTCSessionDescriptionInit;
        const ready = !peer.makingOffer && (pc.signalingState === 'stable' || peer.settingAnswer);
        const collision = description.type === 'offer' && !ready;
        peer.ignoreOffer = this.self < id && collision;
        if (peer.ignoreOffer) return;
        peer.settingAnswer = description.type === 'answer';
        await pc.setRemoteDescription(description);
        peer.settingAnswer = false;
        for (const candidate of peer.candidates.splice(0)) await pc.addIceCandidate(candidate);
        if (description.type === 'offer') {
          for (const t of pc.getTransceivers()) {
            t.direction = 'sendrecv';
            t.sender.setStreams(this.local);
            await t.sender.replaceTrack(
              this.local.getTracks().find((track) => track.kind === t.receiver.track.kind) ?? null,
            );
          }
          await pc.setLocalDescription();
          await this.signal('rtc.answer', { target_id: id, description: pc.localDescription!.toJSON() });
        }
      }
    } catch {
      if (!peer.ignoreOffer && !this.closed) this.onError('映像接続が不安定です。接続を確認してください');
    }
  }

  async updateLocal(stream: MediaStream) {
    this.local = stream;
    for (const { pc } of this.peers.values()) {
      for (const transceiver of pc.getTransceivers()) {
        const kind = transceiver.receiver.track.kind;
        const track = stream.getTracks().find((t) => t.kind === kind) ?? null;
        transceiver.sender.setStreams(stream);
        await transceiver.sender.replaceTrack(track);
      }
    }
  }
  updateConfig(config: RTCConfiguration) {
    this.config = config;
    for (const { pc } of this.peers.values()) pc.setConfiguration(config);
  }
  remove(id: string) {
    this.peers.get(id)?.pc.close();
    this.peers.delete(id);
    this.onStream(id, null);
  }
  close() {
    this.closed = true;
    for (const id of [...this.peers.keys()]) this.remove(id);
  }
}
