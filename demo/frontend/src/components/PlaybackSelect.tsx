import type { PlaybackMode } from '../types/protocol';
import { playbackNames } from '../types/protocol';
import { useI18n } from '../i18n';

export default function PlaybackSelect({
  value,
  onChange,
}: {
  value: PlaybackMode;
  onChange: (value: PlaybackMode) => void;
}) {
  const { t } = useI18n();
  return (
    <label className="control-select playback-select">
      {t('出力')}
      <select aria-label={t('出力')} value={value} onChange={(e) => onChange(e.target.value as PlaybackMode)}>
        {(Object.keys(playbackNames) as PlaybackMode[]).map((mode) => (
          <option key={mode} value={mode}>
            {t(playbackNames[mode])}
          </option>
        ))}
      </select>
    </label>
  );
}
