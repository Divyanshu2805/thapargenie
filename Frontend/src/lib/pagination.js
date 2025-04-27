/** The API returns `next` as a full URL; only its cursor is needed. */
export function cursorFrom(nextUrl) {
  if (!nextUrl) return undefined;
  try {
    return new URL(nextUrl).searchParams.get('cursor') || undefined;
  } catch {
    return undefined;
  }
}
