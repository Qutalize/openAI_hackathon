import { useEffect, useRef, useState, type CSSProperties } from 'react';
import type { Participant } from '../types/protocol';
import { useI18n } from '../i18n';
import Video from './Video';
import ControlIcon from './ControlIcon';
import UserAvatar from './UserAvatar';
import ParticipantActivity from './ParticipantActivity';

export default function SpeakerStage({
  speaker,
  stream,
  self,
  pinned,
  onUnpin,
  children,
}: {
  speaker?: Participant;
  stream?: MediaStream;
  self: string;
  pinned: boolean;
  onUnpin: () => void;
  children?: React.ReactNode;
}) {
  const { t } = useI18n();
  const stage = useRef<HTMLElement>(null);
  const [height, setHeight] = useState(500);
  const [small, setSmall] = useState(() => matchMedia('(max-width: 760px)').matches);
  const [stripHeight, setStripHeight] = useState(() =>
    matchMedia('(max-width: 760px)').matches ? 104 : 154,
  );
  const min = small ? 88 : 112,
    max = Math.max(min, Math.min(height - 72, small ? 220 : 360));
  const clamp = (value: number) => Math.max(min, Math.min(max, value));
  const dragStart = useRef({ y: 0, height: 0 });
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      setHeight(entry.contentRect.height);
      setSmall(matchMedia('(max-width: 760px)').matches);
    });
    if (stage.current) observer.observe(stage.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => setStripHeight((value) => Math.max(min, Math.min(max, value))), [min, max]);
  return (
    <section
      ref={stage}
      className="speaker-stage"
      aria-label={t('発話者映像')}
      style={{ '--participants-height': stripHeight + 'px' } as CSSProperties}
    >
      {children}
      <div
        className="panel-divider participants-divider"
        role="separator"
        tabIndex={0}
        aria-label={t('参加者と発話者の映像サイズ')}
        aria-orientation="horizontal"
        aria-valuemin={min}
        aria-valuemax={Math.round(max)}
        aria-valuenow={Math.round(stripHeight)}
        onPointerDown={(event) => {
          event.preventDefault();
          event.currentTarget.setPointerCapture(event.pointerId);
          dragStart.current = { y: event.clientY, height: stripHeight };
        }}
        onPointerMove={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            setStripHeight(clamp(dragStart.current.height + event.clientY - dragStart.current.y));
        }}
        onPointerUp={(event) => event.currentTarget.releasePointerCapture(event.pointerId)}
        onKeyDown={(event) => {
          if (['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
            event.preventDefault();
            setStripHeight((value) =>
              event.key === 'Home'
                ? min
                : event.key === 'End'
                  ? max
                  : clamp(value + (event.key === 'ArrowUp' ? -8 : 8)),
            );
          }
        }}
      >
        <span />
      </div>
      <div className="main-video">
        {speaker?.devices.camera && stream ? (
          <Video
            stream={stream}
            local={speaker.id === self}
            label={t('{name}の発話者映像', { name: speaker.display_name })}
          />
        ) : (
          <div className="stage-placeholder">
            <span className="stage-symbol">
              <UserAvatar avatar={speaker?.avatar} name={speaker?.display_name} size={64} />
            </span>
            <p>{speaker ? speaker.display_name : t('会話の準備ができました')}</p>
            <small>{t(speaker ? 'カメラはOFFです' : '参加者を待っています')}</small>
          </div>
        )}
      </div>
      <div className="speaker-footer">
        {speaker && (
          <span className="speaker-name">
            <UserAvatar avatar={speaker.avatar} name={speaker.display_name} size={22} />
            <span title={speaker.display_name}>{speaker.display_name}</span>
            <ParticipantActivity participant={speaker} />
            <span
              aria-label={t('マイク') + (speaker.devices.microphone ? ' ON' : ' OFF')}
              title={t('マイク') + (speaker.devices.microphone ? ' ON' : ' OFF')}
            >
              <ControlIcon kind="mic" off={!speaker.devices.microphone} size={16} />
            </span>
            <span
              aria-label={t('カメラ') + (speaker.devices.camera ? ' ON' : ' OFF')}
              title={t('カメラ') + (speaker.devices.camera ? ' ON' : ' OFF')}
            >
              <ControlIcon kind="camera" off={!speaker.devices.camera} size={16} />
            </span>
          </span>
        )}
        {pinned && (
          <button className="unpin secondary" onClick={onUnpin}>
            {t('自動表示へ')}
          </button>
        )}
      </div>
    </section>
  );
}
