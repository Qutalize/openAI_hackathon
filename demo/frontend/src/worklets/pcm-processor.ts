declare const sampleRate: number;
declare class AudioWorkletProcessor {
  port: MessagePort;
  constructor();
}
declare function registerProcessor(name: string, processor: typeof AudioWorkletProcessor): void;

class PCMProcessor extends AudioWorkletProcessor {
  private samples: number[] = [];
  private position = 0;
  private pcm: number[] = [];
  process(inputs: Float32Array[][]) {
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++)
      this.samples.push(channels.reduce((sum, ch) => sum + ch[i], 0) / channels.length);
    // Windowed-sinc low-pass interpolation also suppresses aliasing during downsampling.
    const step = sampleRate / 16000,
      radius = 12,
      cutoff = Math.min(1, 16000 / sampleRate) * 0.9;
    while (this.position + radius < this.samples.length) {
      let total = 0,
        weights = 0;
      for (let n = Math.ceil(this.position - radius); n <= Math.floor(this.position + radius); n++) {
        if (n < 0) continue;
        const x = n - this.position;
        const sinc = Math.abs(x) < 1e-8 ? cutoff : Math.sin(Math.PI * cutoff * x) / (Math.PI * x);
        const weight = sinc * (0.5 + 0.5 * Math.cos((Math.PI * x) / radius));
        total += this.samples[n] * weight;
        weights += weight;
      }
      this.pcm.push(Math.round(Math.max(-1, Math.min(1, total / weights)) * 32767));
      this.position += step;
      if (this.pcm.length === 3200) {
        const pcm = new ArrayBuffer(6400),
          view = new DataView(pcm);
        this.pcm.forEach((n, i) => view.setInt16(i * 2, n, true));
        this.port.postMessage(pcm, [pcm]);
        this.pcm = [];
      }
    }
    const remove = Math.max(0, Math.floor(this.position) - radius);
    this.samples.splice(0, remove);
    this.position -= remove;
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
export {};
