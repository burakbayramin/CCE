/* Authenticated same-origin route; never a public or cached remote image URL. */
export function PrivateAvatar({
  id,
  size = 'md',
  describedBy,
}: {
  id: string | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  /** Id of nearby text (e.g. the character's name) so the image is not
   * announced as an unlabelled portrait. The alt text stays constant because
   * the e2e suite locates avatars by it. */
  describedBy?: string;
}) {
  const frame = {
    sm: 'size-14 rounded-lg',
    md: 'size-24 rounded-xl',
    lg: 'size-40 rounded-2xl',
  }[size];

  if (!id) {
    return (
      <div
        aria-hidden
        className={`${frame} grid place-items-center border border-dashed border-line-strong bg-paper-sunk text-ink-400`}
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-1/3" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="9" r="3.25" />
          <path d="M4.75 19.5c1.5-3.25 4-4.75 7.25-4.75s5.75 1.5 7.25 4.75" strokeLinecap="round" />
        </svg>
      </div>
    );
  }

  return (
    // Deliberate: next/image's shared optimizer cache would persist private,
    // per-account authenticated media on a shared CDN path.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/media/${encodeURIComponent(id)}`}
      alt="Önerilen karakter avatarı"
      aria-describedby={describedBy}
      width={160}
      height={160}
      className={`${frame} border border-line bg-paper-sunk object-contain`}
    />
  );
}
