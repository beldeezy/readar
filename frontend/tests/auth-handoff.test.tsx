import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { AuthProvider } from '../src/auth/AuthProvider';
import AuthCallbackPage from '../src/pages/AuthCallbackPage';
import RecommendationsLoadingPage from '../src/pages/RecommendationsLoadingPage';
import ImportReadingHistoryPage from '../src/pages/ImportReadingHistoryPage';
import RecommendationsPage from '../src/pages/RecommendationsPage';
import { AdminRoute, ProtectedRoute } from '../src/App';

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(), exchange: vi.fn(), listener: null as any, profile: vi.fn(),
  preview: vi.fn(), save: vi.fn(), fetch: vi.fn(), getOnboarding: vi.fn(),
}));
vi.mock('../src/auth/supabaseClient', () => ({ supabase: { auth: {
  getSession: mocks.getSession, exchangeCodeForSession: mocks.exchange,
  onAuthStateChange: vi.fn((listener) => { mocks.listener = listener; return { data: { subscription: { unsubscribe: vi.fn() } } }; }),
} } }));
vi.mock('../src/api/client', () => ({
  apiClient: { getCurrentUser: mocks.profile, getOnboarding: mocks.getOnboarding,
    getPreviewRecommendations: mocks.preview, saveOnboarding: mocks.save },
  fetchRecommendations: mocks.fetch, logEvent: vi.fn(), getApiBaseUrlDebug: vi.fn(), RefreshLimitError: class extends Error {},
}));
// Assert delivery through the actual result page; card styling and actions are outside this regression.
vi.mock('../src/components/RecommendationCard', () => ({ default: ({ book }: any) => <p>{book.title}</p> }));
const session = { access_token: 'test-token', user: { id: 'reader', email: 'reader@example.test', created_at: '2026-09-18' } };
const draft = JSON.stringify({ business_stage: 'startup', business_model: 'software', biggest_challenge: 'growth' });
const result = { items: [{ book_id: 'book-1', title: 'The Mom Test', author: 'Rob Fitzpatrick', score: 1 }], request_id: 'request-1' };
function TestLogin() { const nav = useNavigate(); return <button onClick={() => nav('/auth/callback?code=test-code')}>Sign in for test</button>; }
function mount(start: string, strict = true) {
  const app = <AuthProvider><MemoryRouter initialEntries={[start]}><Routes>
    <Route path="/recommendations/loading" element={<RecommendationsLoadingPage />} />
    <Route path="/login" element={<TestLogin />} />
    <Route path="/auth/callback" element={<AuthCallbackPage />} />
    <Route path="/onboarding/import" element={<ImportReadingHistoryPage />} />
    <Route path="/recommendations" element={<ProtectedRoute><RecommendationsPage /></ProtectedRoute>} />
    <Route path="/admin" element={<AdminRoute><p>Admin dashboard</p></AdminRoute>} />
    <Route path="/reading" element={<p>Return to Reading</p>} />
    <Route path="/book/:id" element={<p>Return to selected book</p>} />
    <Route path="/onboarding" element={<p>Start onboarding</p>} />
  </Routes></MemoryRouter></AuthProvider>;
  return render(strict ? <StrictMode>{app}</StrictMode> : app);
}
beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks();
  mocks.getSession.mockResolvedValue({ data: { session: null }, error: null });
  mocks.exchange.mockImplementation(async () => { await Promise.resolve(); mocks.listener('SIGNED_IN', session); return { data: { session }, error: null }; });
  mocks.profile.mockResolvedValue({ is_admin: false });
  mocks.getOnboarding.mockResolvedValue({}); mocks.save.mockReset().mockResolvedValue({});
  mocks.preview.mockResolvedValue(result.items); mocks.fetch.mockResolvedValue(result);
});
afterEach(() => cleanup());
it.each([true, false])('delivers books through preview, authentication, save, import and results (StrictMode=%s)', async strict => {
  // A stalled optional profile lookup must not hold authentication hostage.
  mocks.profile.mockReturnValue(new Promise(() => {}));
  localStorage.setItem('readar_pending_onboarding', draft);
  mount('/recommendations/loading', strict);
  fireEvent.click(await screen.findByText('Sign in for test'));
  fireEvent.click(await screen.findByText('Skip to your picks →'));
  expect(await screen.findByText('The Mom Test')).toBeTruthy();
  expect(mocks.preview).toHaveBeenCalledTimes(1);
  expect(mocks.exchange).toHaveBeenCalledTimes(1);
  expect(mocks.save).toHaveBeenCalledTimes(1);
  expect(mocks.fetch).toHaveBeenCalledTimes(1);
  expect(localStorage.getItem('readar_pending_onboarding')).toBeNull();
});
it('keeps a failed post-login save retryable without showing stale books', async () => {
  localStorage.setItem('readar_pending_onboarding', draft);
  mocks.save.mockRejectedValueOnce(new Error('503')).mockResolvedValueOnce({});
  mount('/auth/callback?code=test-code');
  await screen.findByText('Error loading recommendations');
  expect(mocks.fetch).not.toHaveBeenCalled();
  expect(localStorage.getItem('readar_pending_onboarding')).toBe(draft);
  fireEvent.click(screen.getByText('Try again'));
  fireEvent.click(await screen.findByText('Skip to your picks →'));
  expect(await screen.findByText('The Mom Test')).toBeTruthy();
});
it('resumes pending answers on a protected route after a refresh', async () => {
  mocks.getSession.mockResolvedValue({ data: { session }, error: null });
  localStorage.setItem('readar_pending_onboarding', draft);
  mount('/recommendations');
  fireEvent.click(await screen.findByText('Skip to your picks →'));
  expect(await screen.findByText('The Mom Test')).toBeTruthy();
  expect(mocks.save).toHaveBeenCalledTimes(1);
});
it('does not exchange the OAuth code twice when the callback itself mounts in StrictMode', async () => {
  mount('/auth/callback?code=test-code');
  expect(await screen.findByText('Return to Reading')).toBeTruthy();
  expect(mocks.exchange).toHaveBeenCalledTimes(1);
});
it.each(['stored', 'query'])('preserves an explicit book return link from %s', async source => {
  if (source === 'stored') localStorage.setItem('post_auth_redirect', '/book/book-1');
  mount(`/auth/callback?code=test-code${source === 'query' ? '&next=%2Fbook%2Fbook-1' : ''}`);
  expect(await screen.findByText('Return to selected book')).toBeTruthy();
  expect(screen.queryByText('Return to Reading')).toBeNull();
});
it('takes a new account without saved onboarding to onboarding', async () => {
  mocks.getOnboarding.mockRejectedValue({ response: { status: 404 } });
  mount('/auth/callback?code=test-code');
  expect(await screen.findByText('Start onboarding')).toBeTruthy();
});
it('ignores an external return URL and uses the existing reader’s Reading page', async () => {
  mount('/auth/callback?code=test-code&next=https%3A%2F%2Fexample.test');
  expect(await screen.findByText('Return to Reading')).toBeTruthy();
});
it('loads books for an existing reader on a direct refresh without a health preflight', async () => {
  mocks.getSession.mockResolvedValue({ data: { session }, error: null });
  mount('/recommendations', false);
  expect(await screen.findByText('The Mom Test')).toBeTruthy();
  expect(mocks.save).not.toHaveBeenCalled();
  expect(mocks.fetch).toHaveBeenCalledTimes(1);
});

it('waits for the verified admin role without redirecting during profile lookup', async () => {
  let resolve!: (value: { is_admin: boolean }) => void;
  mocks.profile.mockReturnValue(new Promise(r => { resolve = r; }));
  mocks.getSession.mockResolvedValue({ data: { session }, error: null });
  mount('/admin', false);
  await act(async () => {});
  expect(screen.queryByText('Admin dashboard')).toBeNull();
  expect(screen.getByText('Loading...')).toBeTruthy();
  await act(async () => { resolve({ is_admin: true }); });
  expect(await screen.findByText('Admin dashboard')).toBeTruthy();
});
