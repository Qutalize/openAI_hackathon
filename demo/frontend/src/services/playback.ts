import type { Mode, PlaybackMode, OutputKind } from '../types/protocol';

export function initialPlayback(mode: Mode): PlaybackMode {
  try {
    const value = localStorage.getItem('playback-' + mode);
    if (value === 'captions' || value === 'ai' || value === 'original') return value;
  } catch {
    /* Optional storage. */
  }
  return mode === 'hearing_support' ? 'captions' : mode === 'vision_support' ? 'ai' : 'original';
}
export function outputPreferences(mode: PlaybackMode): OutputKind[] {
  return mode === 'captions' ? ['text'] : ['audio', 'text'];
}
