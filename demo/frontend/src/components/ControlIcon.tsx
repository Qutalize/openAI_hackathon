export type ControlIconKind = 'mic' | 'camera' | 'user' | 'hand' | 'keyboard' | 'audio' | 'edit' | 'leave';
export default function ControlIcon({
  kind,
  off = false,
  size = 22,
}: {
  kind: ControlIconKind;
  off?: boolean;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {kind === 'mic' && (
        <>
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4M8 22h8" />
        </>
      )}
      {kind === 'camera' && (
        <>
          <rect x="2" y="5" width="13" height="14" rx="3" />
          <path d="m15 9 7-4v14l-7-4" />
        </>
      )}
      {kind === 'user' && (
        <>
          <circle cx="12" cy="8" r="4" />
          <path d="M4 22v-2a8 8 0 0 1 16 0v2" />
        </>
      )}
      {kind === 'hand' && (
        <path d="M8 12V5a1.5 1.5 0 0 1 3 0v6-8a1.5 1.5 0 0 1 3 0v8-6a1.5 1.5 0 0 1 3 0v7-3a1.5 1.5 0 0 1 3 0v7c0 4-3 6-7 6-3 0-5-2-6-4l-4-5a1.5 1.5 0 0 1 2-2l3 3" />
      )}
      {kind === 'keyboard' && (
        <>
          <rect x="2" y="5" width="20" height="14" rx="3" />
          <path d="M6 9h.1M10 9h.1M14 9h.1M18 9h.1M6 12h.1M10 12h.1M14 12h.1M18 12h.1M7 16h10" />
        </>
      )}
      {kind === 'audio' && (
        <>
          <path d="m11 3-6 5H2v8h3l6 5zM15 8a6 6 0 0 1 0 8M18 4a11 11 0 0 1 0 16" />
        </>
      )}
      {kind === 'edit' && (
        <>
          <path d="m15 3 6 6M4 15 16 3a2 2 0 0 1 3 0l2 2a2 2 0 0 1 0 3L9 20l-6 1z" />
        </>
      )}
      {kind === 'leave' && (
        <>
          <path d="M9 4H3v16h6M8 12h14m-5-5 5 5-5 5" />
        </>
      )}
      {off && (
        <>
          <path d="m2 2 20 20" strokeWidth="4" stroke="var(--icon-slash-bg, #fff)" />
          <path d="m2 2 20 20" strokeWidth="2" />
        </>
      )}
    </svg>
  );
}
