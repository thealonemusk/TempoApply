/**
 * Job links come from scraped pages and a manual-add endpoint. React renders
 * `href="javascript:..."` as-is, and a script running on the dashboard's origin
 * can read the whole API — the backend trusts this origin with credentials.
 * Only http(s) links are rendered; anything else becomes an inert "#".
 */
export function safeHref(url: string | null | undefined): string {
  const value = (url || '').trim();
  return /^https?:\/\//i.test(value) ? value : '#';
}
