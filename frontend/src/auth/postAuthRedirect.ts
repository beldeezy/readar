const KEY = "post_auth_redirect";

export function setPostAuthRedirect(path: string) {
  try {
    localStorage.setItem(KEY, path);
  } catch {}
}

export function popPostAuthRedirect(): string | null {
  try {
    const val = localStorage.getItem(KEY);
    if (val) localStorage.removeItem(KEY);
    return val;
  } catch {
    return null;
  }
}


/** OAuth always returns inside Readar. Reject protocol-relative and escaped URLs. */
export function safeReturnPath(path: string | null): string | null {
  if (!path || !path.startsWith('/') || path.startsWith('//') || /[\\\x00-\x20]/.test(path)) return null;
  try {
    const decoded = decodeURIComponent(path);
    if (decoded.startsWith('//') || /[\\\x00-\x20]/.test(decoded)) return null;
  } catch { return null; }
  return path;
}
