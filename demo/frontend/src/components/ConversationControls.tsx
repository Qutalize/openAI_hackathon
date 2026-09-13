import type { Conversation } from '../hooks/useConversation';
import type { InputKind, PublicConfig, Session } from '../types/protocol';
import { inputNames } from '../types/protocol';
import { useI18n } from '../i18n';
import ControlIcon from './ControlIcon';
import PlaybackSelect from './PlaybackSelect';

export default function ConversationControls({
  c,
  config,
  session,
}: {
  c: Conversation;
  config: PublicConfig;
  session: Session;
}) {
  const { t } = useI18n();
  const mic = c.devices.stream.getAudioTracks().some((track) => track.readyState === 'live');
  const camera = c.devices.stream.getVideoTracks().some((track) => track.readyState === 'live');
  return (
    <nav className="conversation-controls" aria-label={t('会話の操作')}>
      <button
        className="device-button"
        aria-pressed={mic}
        disabled={c.operating || c.input !== 'speech' || c.state !== 'connected'}
        title={c.input !== 'speech' ? t('この入力方式ではマイクを使用しません') : undefined}
        onClick={() => void c.toggleDevice('audio')}
      >
        <ControlIcon kind="mic" off={!mic} />
        <span>
          {t('マイク')} {mic ? 'ON' : 'OFF'}
        </span>
      </button>
      <button
        className="device-button"
        aria-pressed={camera}
        disabled={c.operating || c.state !== 'connected'}
        onClick={() => void c.toggleDevice('video')}
      >
        <ControlIcon kind="camera" off={!camera} />
        <span>
          {t('カメラ')} {camera ? 'ON' : 'OFF'}
        </span>
      </button>
      <label className="control-select">
        {t('入力')}
        <select
          aria-label={t('入力')}
          value={c.input}
          disabled={c.operating || c.state !== 'connected'}
          onChange={(e) => void c.changeInput(e.target.value as InputKind)}
        >
          {config.modes[session.mode].allowed_inputs.map((kind) => (
            <option
              key={kind}
              value={kind}
              disabled={kind !== 'text' && !config.capabilities[kind].available}
            >
              {t(inputNames[kind])}
              {kind !== 'text' && !config.capabilities[kind].available ? t('（未導入）') : ''}
            </option>
          ))}
        </select>
      </label>
      <PlaybackSelect value={c.playback} onChange={(value) => void c.changeOutput(value)} />
      <button className="participants-button" type="button">
        <ControlIcon kind="user" />
        <span>
          {t('参加者')} {t('{count}人', { count: c.participants.length })}
        </span>
      </button>
      <button className="leave-button" disabled={c.operating} onClick={() => void c.leave()}>
        <ControlIcon kind="leave" />
        <span>{t('会話終了')}</span>
      </button>
    </nav>
  );
}
