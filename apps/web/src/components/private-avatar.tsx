/* Authenticated same-origin route; never a public or cached remote image URL. */
export function PrivateAvatar({ id }: { id: string | null | undefined }) {
  if (!id) return null;
  // next/image's shared optimizer must not cache private authenticated media.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={`/media/${encodeURIComponent(id)}`} alt="Önerilen karakter avatarı" width={192} height={192} className="my-4 max-h-48 rounded object-contain" />;
}
