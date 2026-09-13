import workletURL from '../worklets/pcm-processor.ts?worker&url';

export class AudioCapture {
  context?: AudioContext;
  private source?: MediaStreamAudioSourceNode;
  private node?: AudioWorkletNode;
  async start(stream: MediaStream, onPCM: (buffer: ArrayBuffer) => void) {
    await this.stop();
    if (!stream.getAudioTracks().length) return;
    const context = (this.context = new AudioContext());
    await context.audioWorklet.addModule(workletURL);
    this.source = context.createMediaStreamSource(stream);
    this.node = new AudioWorkletNode(context, 'pcm-processor');
    this.node.port.onmessage = (e) => onPCM(e.data);
    const mute = context.createGain();
    mute.gain.value = 0;
    this.source.connect(this.node).connect(mute).connect(context.destination);
    await context.resume();
  }
  async resume() {
    await this.context?.resume();
  }
  async stop() {
    this.node?.disconnect();
    this.source?.disconnect();
    if (this.context && this.context.state !== 'closed') await this.context.close();
    this.context = undefined;
  }
}
