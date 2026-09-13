import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import type { PublicConfig, Session } from '../types/protocol';
import { useConversation } from '../hooks/useConversation';
import { LanguageSelect, useI18n } from '../i18n';
import DeviceSetup from './DeviceSetup';
import ParticipantStrip from '../components/ParticipantStrip';
import SpeakerStage from '../components/SpeakerStage';
import TranscriptPanel from '../components/TranscriptPanel';
import RecognitionComposer from '../components/RecognitionComposer';
import ConversationControls from '../components/ConversationControls';
import RemoteAudio from '../components/RemoteAudio';
import NameEditor from '../components/NameEditor';

export default function TalkPage({
  config,
  session,
  onLeave,
}: {
  config: PublicConfig;
  session: Session;
  onLeave: (message: string) => void;
}) {
  const c = useConversation(config, session, onLeave),
    { t } = useI18n();
  const [pinned, setPinned] = useState<string | null>(null);
  const [split, setSplit] = useState(62),
    [vertical, setVertical] = useState(() => matchMedia('(max-width: 760px)').matches);
  const grid = useRef<HTMLDivElement>(null);
  const [panelHeight, setPanelHeight] = useState(600);
  const min = vertical ? Math.min(60, Math.max(20, Math.ceil(16000 / Math.max(1, panelHeight)))) : 35;
  const max = vertical ? 60 : 72;
  useEffect(() => {
    if (!c.started || !grid.current) return;
    const observer = new ResizeObserver(([entry]) => setPanelHeight(entry.contentRect.height));
    observer.observe(grid.current);
    return () => observer.disconnect();
  }, [c.started]);
  useEffect(() => {
    setSplit((value) => Math.max(min, Math.min(max, value)));
  }, [min, max]);
  useEffect(() => {
    const query = matchMedia('(max-width: 760px)');
    const change = () => {
      setVertical(query.matches);
      setSplit(query.matches ? 35 : 62);
    };
    change();
    query.addEventListener('change', change);
    return () => query.removeEventListener('change', change);
  }, []);
  useEffect(() => {
    if (pinned && !c.participants.some((p) => p.id === pinned)) setPinned(null);
  }, [c.participants, pinned]);
  const onPlaybackError = useCallback(
    () => c.setError('音声を再生できません。「音声を開始」を押してください'),
    [c.setError],
  );
  if (!c.started) return <DeviceSetup c={c} session={session} />;
  const main =
    c.participants.find((p) => p.id === (pinned ?? c.speaker)) ??
    c.participants.find((p) => p.id !== session.participant_id) ??
    c.participants[0];
  const connected = c.state === 'connected';
  const clamp = (value: number) => Math.max(min, Math.min(max, value));
  const drag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId) || !grid.current) return;
    const box = grid.current.getBoundingClientRect();
    setSplit(
      clamp(
        100 * (vertical ? (event.clientY - box.top) / box.height : (event.clientX - box.left) / box.width),
      ),
    );
  };
  return (
    <main className="talk-page">
      <header className="room-heading">
        <span className="room-brand">{t(config.name)}</span>
        <span className="room-id">
          {t('ルーム')} {session.room_id}
        </span>
        <NameEditor name={c.displayName} onSave={c.rename} avatar={session.avatar} />
        <span className={'connection-label ' + (connected ? 'online' : '')} role="status">
          {t(connected ? '接続中' : c.state === 'expired' ? 'セッションが切れました' : '再接続しています…')}
        </span>
        <LanguageSelect />
      </header>
      <h1 className="sr-only">{t('会話画面')}</h1>
      {c.error && (
        <div className="error room-error" role="alert">
          <span>{t(c.error)}</span>
          <button className="text-button" onClick={() => c.setError('')} aria-label={t('通知を閉じる')}>
            {t('閉じる')}
          </button>
        </div>
      )}
      {c.state === 'expired' && (
        <button className="primary" onClick={() => void c.leave()}>
          {t('入室画面へ戻る')}
        </button>
      )}
      <div
        className="conversation-grid"
        ref={grid}
        style={
          {
            '--video-share': split + '%',
            '--video-ratio': split,
            '--text-ratio': 100 - split,
          } as CSSProperties
        }
      >
        <div className="video-column">
          <SpeakerStage
            speaker={main}
            stream={main ? c.streams[main.id] : undefined}
            self={session.participant_id}
            pinned={!!pinned}
            onUnpin={() => setPinned(null)}
          >
            <ParticipantStrip
              participants={c.participants}
              streams={c.streams}
              self={session.participant_id}
              pinned={pinned}
              onPin={(id) => setPinned(pinned === id ? null : id)}
            />
          </SpeakerStage>
          <div className="stage-status">
            <span role="status" title={t(c.recognition)}>
              {t(c.recognition)}
            </span>
            <span
              className={
                'recording-status ' + (c.recordingStatus === '自分のカメラを録画中' ? 'recording' : '')
              }
              role="status"
            >
              {t(c.recordingStatus)}
            </span>
          </div>
        </div>
        <div
          className="panel-divider"
          role="separator"
          tabIndex={0}
          aria-label={t('映像と文字おこしのサイズ')}
          aria-orientation={vertical ? 'horizontal' : 'vertical'}
          aria-controls="transcript-panel"
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={Math.round(split)}
          onPointerDown={(event) => {
            event.preventDefault();
            event.currentTarget.setPointerCapture(event.pointerId);
            drag(event);
          }}
          onPointerMove={drag}
          onPointerUp={(event) => event.currentTarget.releasePointerCapture(event.pointerId)}
          onKeyDown={(event) => {
            if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
              event.preventDefault();
              setSplit((value) =>
                event.key === 'Home'
                  ? min
                  : event.key === 'End'
                    ? max
                    : clamp(value + (['ArrowLeft', 'ArrowUp'].includes(event.key) ? -2 : 2)),
              );
            }
          }}
        >
          <span />
        </div>
        <TranscriptPanel
          utterances={c.utterances}
          readingId={c.readingId}
          self={session.participant_id}
          onCorrect={c.correct}
          avatars={c.avatars}
        >
          <RecognitionComposer
            input={c.input}
            candidate={c.candidate}
            capturing={c.capturing}
            processing={c.processing}
            connected={connected}
            config={config}
            onStart={c.beginCapture}
            onEnd={c.endCapture}
            onSubmit={c.submit}
            onCancel={() => void c.cancelRecognition()}
          />
        </TranscriptPanel>
      </div>
      <div className="meeting-utilities">
        <div className="auxiliary-buttons">
          <button
            className="secondary"
            disabled={c.playback === 'captions'}
            onClick={() => void c.startSound()}
          >
            {t('音声を開始')}
          </button>
          <button className="secondary" disabled={c.playback === 'captions'} onClick={c.stopSpeech}>
            {t('読み上げ停止')}
          </button>
          <button className="secondary" disabled={c.playback === 'captions'} onClick={c.replayUnread}>
            {t('未読を再生')}
          </button>
        </div>
        {c.playback !== 'captions' &&
          !['待機中', '停止', '読み上げ中', '読み上げ一時停止中'].includes(c.ttsStatus) && (
            <span className="tts-notice" role="status">
              {t(c.ttsStatus)}
            </span>
          )}
      </div>
      <ConversationControls c={c} config={config} session={session} />
      {Object.entries(c.streams)
        .filter(([id]) => id !== session.participant_id)
        .map(([id, stream]) => (
          <RemoteAudio
            key={id}
            stream={stream}
            enabled={c.playback === 'original'}
            onError={onPlaybackError}
          />
        ))}
    </main>
  );
}
