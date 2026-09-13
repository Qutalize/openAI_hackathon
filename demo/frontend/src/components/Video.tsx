import { useEffect, useRef } from 'react';

export default function Video({
  stream,
  local = false,
  label,
  onPlaybackError,
}: {
  stream?: MediaStream;
  local?: boolean;
  label: string;
  onPlaybackError?: () => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (v) {
      v.srcObject = stream ?? null;
      v.play().catch(() => onPlaybackError?.());
    }
    return () => {
      if (v) v.srcObject = null;
    };
  }, [stream, onPlaybackError]);
  return (
    <video ref={ref} autoPlay muted playsInline aria-label={label} className={local ? 'mirrored' : ''} />
  );
}
