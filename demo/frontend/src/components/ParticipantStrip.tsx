import type { Participant, VideoStatus } from '../types/protocol';
import { VIDEO_MESSAGES } from './SpeakerStage';
import { useI18n } from '../i18n';
import Video from './Video';
import ControlIcon from './ControlIcon';
import UserAvatar from './UserAvatar';
import ParticipantActivity from './ParticipantActivity';

export default function ParticipantStrip({
  participants,
  streams,
  statuses,
  self,
  pinned,
  onPin,
}: {
  participants: Participant[];
  streams: Record<string, MediaStream>;
  statuses: Record<string, VideoStatus>;
  self: string;
  pinned: string | null;
  onPin: (id: string) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="participant-strip" aria-label={t('参加者の映像')}>
      {participants.map((p) => (
        <button
          key={p.id}
          className={'participant-tile ' + (pinned === p.id ? 'pinned' : '')}
          onClick={() => onPin(p.id)}
          aria-pressed={pinned === p.id}
          aria-label={t('{name}の映像を固定', { name: p.display_name })}
        >
          <span className="tile-heading">
            <UserAvatar avatar={p.avatar} name={p.display_name} size={22} />
            <span title={p.display_name}>
              {p.display_name}
              {p.id === self ? ' (' + t('自分') + ')' : ''}
            </span>
          </span>
          <div className="tile-video">
            {statuses[p.id] === 'live' && streams[p.id] ? (
              <Video
                stream={streams[p.id]}
                local={p.id === self}
                label={t('{name}のカメラ', { name: p.display_name })}
              />
            ) : (
              <div className="tile-placeholder">
                <UserAvatar avatar={p.avatar} name={p.display_name} size={36} />
                {statuses[p.id] && statuses[p.id] !== 'off' && (
                  <small className={statuses[p.id] === 'failed' ? 'video-problem' : undefined}>
                    {t(VIDEO_MESSAGES[statuses[p.id]])}
                  </small>
                )}
              </div>
            )}
          </div>
          <span className="tile-devices">
            <ParticipantActivity participant={p} />
            <span
              title={t('マイク') + (p.devices.microphone ? ' ON' : ' OFF')}
              aria-label={t('マイク') + (p.devices.microphone ? ' ON' : ' OFF')}
            >
              <ControlIcon kind="mic" off={!p.devices.microphone} size={16} />
            </span>
            <span
              title={t('カメラ') + (p.devices.camera ? ' ON' : ' OFF')}
              aria-label={t('カメラ') + (p.devices.camera ? ' ON' : ' OFF')}
            >
              <ControlIcon kind="camera" off={!p.devices.camera} size={16} />
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}
