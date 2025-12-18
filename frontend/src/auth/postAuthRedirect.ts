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

