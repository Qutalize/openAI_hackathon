import { useCallback, useEffect, useRef, useState } from 'react';
import type { PublicConfig } from '../types/protocol';

export function useDevices(config: PublicConfig, onError: (message: string) => void) {
  const streamRef = useRef(new MediaStream());
  const sources = useRef(new Map<string, MediaStream>());
  const [stream, setStream] = useState(streamRef.current);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);
  const update = useCallback(
    async (kind: 'audio' | 'video', enabled: boolean) => {
      if (enabled && !navigator.mediaDevices?.getUserMedia)
        throw new Error('カメラ・マイクにはHTTPSまたはlocalhostが必要です');
      setBusy(true);
      try {
        const current = streamRef.current;
        for (const track of current.getTracks().filter((t) => t.kind === kind)) {
          track.stop();
          current.removeTrack(track);
        }
        sources.current.delete(kind);
        if (enabled) {
          const obtained = await navigator.mediaDevices.getUserMedia(
            kind === 'audio'
              ? {
                  audio: {
                    echoCancellation: config.media.echo_cancellation,
                    noiseSuppression: config.media.noise_suppression,
                  },
                }
              : {
                  video: {
                    width: { ideal: config.media.video_width },
                    height: { ideal: config.media.video_height },
                    frameRate: { ideal: config.media.video_fps },
                  },
                },
          );
          if (!mounted.current) {
            obtained.getTracks().forEach((t) => t.stop());
            return current;
          }
          sources.current.set(kind, obtained);
          obtained.getTracks().forEach((track) => {
            track.onended = () => {
              current.removeTrack(track);
              const next = new MediaStream(current.getTracks());
              streamRef.current = next;
              setStream(next);
              onError('機器が切断されました。再度ONにしてください');
            };
            current.addTrack(track);
          });
        }
        const next = new MediaStream(current.getTracks());
        streamRef.current = next;
        setStream(next);
        return next;
      } catch (error) {
        setStream(new MediaStream(streamRef.current.getTracks()));
        const e = error as DOMException;
        throw new Error(
          e.name === 'NotAllowedError'
            ? '権限が許可されていません。ブラウザ設定を確認するか、文字入力をご利用ください'
            : e.name === 'NotFoundError'
              ? 'カメラまたはマイクが見つかりません'
              : e.message,
        );
      } finally {
        setBusy(false);
      }
    },
    [config, onError],
  );
  const stop = useCallback(() => {
    streamRef.current.getTracks().forEach((t) => t.stop());
    sources.current.clear();
    streamRef.current = new MediaStream();
    setStream(streamRef.current);
  }, []);
  useEffect(
    () => () => {
      mounted.current = false;
      streamRef.current.getTracks().forEach((t) => t.stop());
      sources.current.clear();
    },
    [],
  );
  return { stream, streamRef, update, stop, busy };
}
