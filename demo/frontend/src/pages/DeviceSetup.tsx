import type { Conversation } from '../hooks/useConversation';
import type { Session } from '../types/protocol';
import { inputNames } from '../types/protocol';
import { LanguageSelect, useI18n } from '../i18n';
import Video from '../components/Video';
import NameEditor from '../components/NameEditor';
import ControlIcon from '../components/ControlIcon';
import PlaybackSelect from '../components/PlaybackSelect';

export default function DeviceSetup({ c, session }: { c: Conversation; session: Session }) {
  const { t } = useI18n();
  const camera = !!c.devices.stream.getVideoTracks().length,
    mic = !!c.devices.stream.getAudioTracks().length;
  return (
    <main className="device-setup">
      <div className="page-language">
        <LanguageSelect />
      </div>
      <p className="eyebrow">{t('もうすぐ会話がはじまります')}</p>
      <h1>{t('カメラと音声を確認')}</h1>
      <NameEditor name={c.displayName} onSave={c.rename} avatar={session.avatar} />
      <p>
        {t('ルーム')} {session.room_id} · {t('入力')}: {t(inputNames[c.input])}
      </p>
      <div className="setup-preview">
        {camera ? (
          <Video stream={c.devices.stream} local label={t('自分のカメラプレビュー')} />
        ) : (
          <p>{t('カメラはOFFです')}</p>
        )}
      </div>
      <div className="setup-buttons">
        <button className="secondary" disabled={c.operating} onClick={() => void c.toggleDevice('video')}>
          <ControlIcon kind="camera" off={!camera} />
          {t(camera ? 'カメラをOFF' : 'カメラをON')}
        </button>
        {c.input === 'speech' && (
          <button className="secondary" disabled={c.operating} onClick={() => void c.toggleDevice('audio')}>
            <ControlIcon kind="mic" off={!mic} />
            {t(mic ? 'マイクをOFF' : 'マイクをON')}
          </button>
        )}
      </div>
      <p className="setup-guidance">{t('機器をONにすると、ブラウザから利用許可を求められます。')}</p>
      <div className="setup-output">
        <PlaybackSelect value={c.playback} onChange={(value) => void c.changeOutput(value)} />
      </div>
      <p className="recording-notice">
        {t(
          '会話開始後、カメラがONの間は自分の映像だけを録画します。カメラOFFで録画を停止し、会話終了時に端末へ保存します。',
        )}
      </p>
      {c.error && (
        <p className="error" role="alert">
          {t(c.error)}
        </p>
      )}
      <div className="setup-buttons">
        <button className="primary" disabled={c.operating} onClick={() => void c.startConversation()}>
          {t('会話を開始')}
        </button>
        <button className="secondary" disabled={c.operating} onClick={() => void c.startConversation(true)}>
          {t('文字表示で参加')}
        </button>
        <button className="text-button" onClick={() => void c.leave()}>
          {t('参加を中止')}
        </button>
      </div>
    </main>
  );
}
