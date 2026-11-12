import type { Mode } from '../types/protocol';
import { modeNames } from '../types/protocol';
import { useI18n } from '../i18n';

export default function ModeCard({
  mode,
  selected,
  onSelect,
}: {
  mode: Mode;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useI18n();
  return (
    <label className={'mode-card ' + (selected ? 'selected' : '')}>
      <input type="radio" name="mode" value={mode} checked={selected} onChange={onSelect} />
      <span className="mode-check" aria-hidden="true">
        {selected ? '✓' : ''}
      </span>
      <span className="mode-title">{t(modeNames[mode])}</span>
      <span className="mode-description">
        {t(
          mode === 'hearing_support'
            ? '聞こえにくい方向け。手話で話し、字幕で受け取ります'
            : mode === 'vision_support'
              ? '見えにくい方向け。声で話し、音声で受け取ります'
              : '声や口の動きで話し、音声と字幕で受け取ります',
        )}
      </span>
    </label>
  );
}
