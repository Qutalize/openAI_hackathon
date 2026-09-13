import type { InputKind } from '../types/protocol';
export default function Icon({ kind, size = 48 }: { kind: InputKind | 'audio'; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      aria-hidden="true"
    >
      {kind === 'speech' || kind === 'audio' ? (
        <>
          <rect x="24" y="7" width="16" height="31" rx="8" />
          <path d="M16 29v3a16 16 0 0 0 32 0v-3M32 48v9M22 57h20" />
        </>
      ) : kind === 'lipread' ? (
        <>
          <path d="M4 30c12 0 18-15 28-8 10-7 16 8 28 8-5 15-15 23-28 23S9 45 4 30Z" fill="#ff91a3" />
          <path d="M4 30c16 8 40 8 56 0" />
        </>
      ) : kind === 'sign' ? (
        <>
          <path
            d="M19 34V16a4 4 0 0 1 8 0v14-20a4 4 0 0 1 8 0v20-15a4 4 0 0 1 8 0v17-8a4 4 0 0 1 8 0v19c0 11-8 16-18 16-7 0-12-4-15-10L9 34a4 4 0 0 1 7-4l7 9"
            fill="#ffdcba"
          />
        </>
      ) : (
        <>
          <path d="M15 5h25l12 12v42H15Z" />
          <path d="M40 5v14h12M23 30h21M23 39h21M23 48h15" />
        </>
      )}
    </svg>
  );
}
