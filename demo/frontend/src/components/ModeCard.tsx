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
      <span className="mode-caption">{t('入力')}</span>
      <span className="mode-description">
        {t(mode === 'hearing_support' ? '手話' : mode === 'vision_support' ? '発声' : '発声・読唇')}
      </span>
      <span className="mode-caption output-caption">{t('出力')}</span>
      <span className="mode-description">
        {t(mode === 'standard' ? '音声・文字' : mode === 'vision_support' ? '音声' : '文字')}
      </span>
    </label>
  );
}
