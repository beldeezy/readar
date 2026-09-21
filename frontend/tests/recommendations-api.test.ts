import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fetchRecommendations, RefreshLimitError } from '../src/api/client';
vi.mock('../src/auth/supabaseClient', () => ({ supabase: { auth: {} } }));
beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('fetch', vi.fn()); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
it('bounds a stalled network call and aborts the request', async () => {
  vi.mocked(fetch).mockReturnValue(new Promise(() => {}));
  const assertion = expect(fetchRecommendations({ limit: 5 })).rejects.toThrow('taking longer');
  await vi.advanceTimersByTimeAsync(20001); await assertion;
  expect((vi.mocked(fetch).mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});
it('also bounds a stalled response body after HTTP 200', async () => {
  vi.mocked(fetch).mockResolvedValue({ ok: true, status: 200, json: () => new Promise(() => {}) } as Response);
  const assertion = expect(fetchRecommendations({})).rejects.toThrow('taking longer');
  await vi.advanceTimersByTimeAsync(20001); await assertion;
});
it('rejects a malformed success response and clears the deadline', async () => {
  vi.mocked(fetch).mockResolvedValue({ ok: true, status: 200, json: async () => ({ detail: 'not books' }) } as Response);
  await expect(fetchRecommendations({})).rejects.toThrow('could not read');
  expect(vi.getTimerCount()).toBe(0);
});
it('preserves typed refresh-limit errors for the existing upgrade prompt', async () => {
  vi.mocked(fetch).mockResolvedValue({ ok: false, status: 429 } as Response);
  await expect(fetchRecommendations({ spin: true })).rejects.toBeInstanceOf(RefreshLimitError);
  expect(vi.getTimerCount()).toBe(0);
});
it('returns valid books without leaving a deadline timer behind', async () => {
  const result = { items: [{ book_id: 'book-1', title: 'The Mom Test' }], request_id: 'test' };
  vi.mocked(fetch).mockResolvedValue({ ok: true, status: 200, json: async () => result } as Response);
  await expect(fetchRecommendations({})).resolves.toEqual(result);
  expect(vi.getTimerCount()).toBe(0);
});
