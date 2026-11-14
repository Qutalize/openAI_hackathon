import type { Capability, InputKind, PublicConfig, VisionLanguage } from '../types/protocol';

const UNAVAILABLE: Capability = { available: false, reason: 'モデル未導入', vocabulary: [] };

/** Lip reading and signing run a Japanese phrase model or an English open-vocabulary model. */
export function capabilityKey(kind: InputKind, language: VisionLanguage) {
  return (kind === 'lipread' || kind === 'sign') && language === 'en' ? (`${kind}_open` as const) : kind;
}

export function capability(
  config: PublicConfig,
  kind: InputKind,
  language: VisionLanguage = 'ja',
): Capability {
  if (kind === 'text') return { available: true, reason: '', vocabulary: [] };
  return (
    config.capabilities[capabilityKey(kind, language) as keyof PublicConfig['capabilities']] ?? UNAVAILABLE
  );
}

export function languages(config: PublicConfig, kind: InputKind): VisionLanguage[] {
  if (kind !== 'lipread' && kind !== 'sign') return ['ja'];
  return (['ja', 'en'] as const).filter((x) => capability(config, kind, x).available);
}

export function inputAvailable(config: PublicConfig, kind: InputKind) {
  return kind === 'text' || languages(config, kind).some((x) => capability(config, kind, x).available);
}

export function defaultLanguage(config: PublicConfig, kind: InputKind): VisionLanguage {
  return languages(config, kind)[0] ?? 'ja';
}

/** The reason shown when no language of an input is available. */
export function unavailableReason(config: PublicConfig, kind: InputKind) {
  return capability(config, kind, 'ja').reason;
}
