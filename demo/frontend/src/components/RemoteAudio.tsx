import { useEffect, useRef } from 'react';
export default function RemoteAudio({
  stream,
  enabled,
  onError,
}: {
  stream: MediaStream;
  enabled: boolean;
  onError: () => void;
}) {
  const ref = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    const a = ref.current!;
    a.srcObject = stream;
    if (enabled) a.play().catch(onError);
    return () => {
      a.pause();
      a.srcObject = null;
    };
  }, [stream, enabled, onError]);
  return <audio ref={ref} autoPlay muted={!enabled} />;
}
