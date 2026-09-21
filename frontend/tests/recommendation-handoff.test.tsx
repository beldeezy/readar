import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import RecommendationsLoadingPage from '../src/pages/RecommendationsLoadingPage';

const mocks = vi.hoisted(() => ({
  auth: { user: null as null | { id: string }, loading: false, hasVerifiedMagicLink: false,
    setHasVerifiedMagicLink: vi.fn(), refreshOnboardingStatus: vi.fn().mockResolvedValue(undefined) },
  preview: vi.fn(), save: vi.fn(), fetch: vi.fn(), event: vi.fn(),
}));
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => mocks.auth }));
vi.mock('../src/api/client', () => ({
  apiClient: { getPreviewRecommendations: mocks.preview, saveOnboarding: mocks.save, getOnboarding: vi.fn() },
  fetchRecommendations: mocks.fetch, logEvent: mocks.event,
}));
const draft = JSON.stringify({ business_stage: 'startup', business_model: 'software', biggest_challenge: 'growth' });
const books = [{ id: 'book-1', title: 'The Mom Test' }];
function Destination() { const location = useLocation(); return <p>{location.pathname} {JSON.stringify(location.state)}</p>; }
function Leave() { const navigate = useNavigate(); return <button onClick={() => navigate('/away')}>Leave</button>; }
function mount(strict = true) {
  const app = <MemoryRouter initialEntries={['/recommendations/loading']}><Leave /><Routes>
    <Route path="/recommendations/loading" element={<RecommendationsLoadingPage />} />
    <Route path="*" element={<Destination />} />
  </Routes></MemoryRouter>;
  return render(strict ? <StrictMode>{app}</StrictMode> : app);
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); mocks.auth.user = null; mocks.auth.loading = false; mocks.preview.mockReset(); mocks.fetch.mockReset(); mocks.save.mockReset().mockResolvedValue({}); });
afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('recommendation handoff', () => {
  it('advances a successful preview to sign-in under StrictMode', async () => {
    vi.useFakeTimers(); localStorage.setItem('readar_pending_onboarding', draft);
    const response = deferred<typeof books>(); mocks.preview.mockReturnValue(response.promise);
    mount();
    await act(async () => { response.resolve(books); await response.promise; });
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.queryByText(/\/login/)).not.toBeNull();
    expect(mocks.preview).toHaveBeenCalledTimes(1);
    expect(JSON.parse(localStorage.getItem('readar_preview_recs')!)).toEqual(books);
    expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
  });
});

it.each([true, false])('saves the latest answers and delivers fetched books through import (StrictMode=%s)', async strict => {
  mocks.auth.user = { id: 'reader' }; localStorage.setItem('readar_pending_onboarding', draft);
  mocks.fetch.mockResolvedValue({ items: books, request_id: 'request-1', refreshes_remaining: 2 });
  mount(strict);
  expect(await screen.findByText(/\/onboarding\/import/)).toBeTruthy();
  expect(mocks.save).toHaveBeenCalledTimes(1);
  expect(mocks.fetch).toHaveBeenCalledTimes(1);
  expect(screen.getByText(/The Mom Test/)).toBeTruthy();
  expect(localStorage.getItem('readar_pending_onboarding')).toBeNull();
});
it('waits for session restoration before starting a preview', async () => {
  mocks.auth.loading = true; localStorage.setItem('readar_pending_onboarding', draft);
  const app = mount(); expect(mocks.preview).not.toHaveBeenCalled(); app.unmount();
});
it('preserves answers on a failed save and retries without reloading', async () => {
  mocks.auth.user = { id: 'reader' }; localStorage.setItem('readar_pending_onboarding', draft);
  mocks.save.mockRejectedValueOnce(new Error('503')).mockResolvedValueOnce({});
  mocks.fetch.mockResolvedValue({ items: books }); mount();
  await screen.findByText('Error loading recommendations');
  expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
  expect(mocks.fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByText(/\/onboarding\/import/);
  expect(mocks.save).toHaveBeenCalledTimes(2);
});
it.each(['preview', 'authenticated'])('shows an actionable empty-result state for %s', async flow => {
  localStorage.setItem('readar_pending_onboarding', draft);
  if (flow === 'authenticated') mocks.auth.user = { id: 'reader' };
  mocks.preview.mockResolvedValue([]); mocks.fetch.mockResolvedValue({ items: [] }); mount();
  await screen.findByText('Error loading recommendations');
  expect(screen.getByText(/could not find your books/)).toBeTruthy();
  expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
});
it('times out a stalled request, supports retry, and ignores its late response', async () => {
  vi.useFakeTimers(); localStorage.setItem('readar_pending_onboarding', draft);
  const late = deferred<typeof books>(); mocks.preview.mockReturnValueOnce(late.promise).mockResolvedValueOnce(books);
  mount(); await act(async () => { await vi.advanceTimersByTimeAsync(20001); });
  expect(screen.getByText(/taking longer/)).toBeTruthy();
  expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await act(async () => {});
  expect(screen.getByText(/\/login/)).toBeTruthy();
  await act(async () => { late.resolve([{ id: 'late', title: 'Stale result' }]); });
  expect(JSON.parse(localStorage.getItem('readar_preview_recs')!)).toEqual(books);
});
it('does not navigate or discard answers when a request completes after leaving', async () => {
  mocks.auth.user = { id: 'reader' }; localStorage.setItem('readar_pending_onboarding', draft);
  const response = deferred<{ items: typeof books }>(); mocks.fetch.mockReturnValue(response.promise);
  mount(); await act(async () => {});
  fireEvent.click(screen.getByText('Leave'));
  await act(async () => { response.resolve({ items: books }); });
  expect(screen.getByText(/\/away/)).toBeTruthy();
  expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
});
it('loads existing readers directly and supports a fresh visit after unmount', async () => {
  mocks.auth.user = { id: 'reader' }; mocks.fetch.mockResolvedValue({ items: books });
  const first = mount(); await screen.findByText(/\/recommendations /); first.unmount();
  mount(); await screen.findByText(/\/recommendations /);
  expect(mocks.save).not.toHaveBeenCalled(); expect(mocks.fetch).toHaveBeenCalledTimes(2);
});
