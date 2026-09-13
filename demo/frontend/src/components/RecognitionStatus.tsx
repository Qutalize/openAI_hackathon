export default function RecognitionStatus({
  name,
  status,
  tts,
  outputAudio,
  readerNotifications,
}: {
  name: string;
  status: string;
  tts: string;
  outputAudio: boolean;
  readerNotifications: boolean;
}) {
  return (
    <div className="status-bars">
      <p role={readerNotifications ? 'status' : undefined}>
        <span className="status-dot" />
        {name}：{status}
      </p>
      <p>補助読み上げ：{outputAudio ? tts : 'OFF'}</p>
    </div>
  );
}
