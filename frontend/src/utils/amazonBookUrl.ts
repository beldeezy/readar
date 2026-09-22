/** Keep existing Amazon affiliate links; otherwise search by known book details. */
export function amazonBookUrl(purchaseUrl?: string | null, title?: string | null, author?: string | null): string | null {
  if (purchaseUrl) {
    try {
      const url = new URL(purchaseUrl);
      const domains = ['amazon.com', 'amazon.co.uk', 'amazon.ca', 'amazon.com.au', 'amzn.to'];
      if (url.protocol === 'https:' && !url.username && !url.password &&
        domains.some(domain => url.hostname === domain || url.hostname.endsWith(`.${domain}`))) return url.href;
    } catch { /* Use the catalog title if the stored link is unavailable. */ }
  }
  if (!title?.trim()) return null;
  return `https://www.amazon.com/s?k=${encodeURIComponent(`${title.trim()} ${author?.trim() || ''}`.trim())}`;
}
