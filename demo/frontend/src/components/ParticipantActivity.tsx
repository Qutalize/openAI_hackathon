import type { Participant } from '../types/protocol';
import { useI18n } from '../i18n';

export default function ParticipantActivity({ participant }: { participant: Participant }) {
  const { t } = useI18n();
  if (participant.connection_state !== 'connected') return null;
  return (
    <span className="participant-activity">
      {participant.speaking && <span className="speaking-indicator">{t('発話中')}</span>}
      {participant.recognizing && <span className="recognizing-indicator">{t('認識中')}</span>}
    </span>
  );
}
