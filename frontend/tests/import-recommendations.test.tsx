import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import ImportReadingHistoryPage from '../src/pages/ImportReadingHistoryPage';
import RecommendationsPage from '../src/pages/RecommendationsPage';

const mocks = vi.hoisted(() => ({ upload: vi.fn(), fetch: vi.fn() }));
vi.mock('../src/api/client', () => ({
  apiClient: { uploadReadingHistoryCsv: mocks.upload }, fetchRecommendations: mocks.fetch,
  logEvent: vi.fn(), RefreshLimitError: class extends Error {},
}));
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => ({ user: { id: 'reader' } }) }));
vi.mock('../src/components/RecommendationCard', () => ({ default: ({ book }: { book: { title: string } }) => <p>{book.title}</p> }));

const stale = [{ book_id: 'old', title: 'Previously read book' }];
const fresh = { items: [{ book_id: 'new', title: 'Fresh unread match' }], request_id: 'fresh' };
function routes() {
  return <Routes>
    <Route path="/onboarding/import" element={<ImportReadingHistoryPage />} />
    <Route path="/recommendations" element={<RecommendationsPage />} />
  </Routes>;
}
function mount() {
  return render(<StrictMode><MemoryRouter initialEntries={[{ pathname: '/onboarding/import', state: { prefetchedRecommendations: stale } }]}>{routes()}</MemoryRouter></StrictMode>);
}
async function upload() {
  fireEvent.change(screen.getByLabelText('Goodreads CSV file'), { target: { files: [new File(['Title,Author\nBook,Writer'], 'books.csv')] } });
  await act(async () => {});
}
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear();
  mocks.upload.mockResolvedValue({ imported_count: 4, skipped_count: 1 });
  mocks.fetch.mockResolvedValue(fresh);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

it('does not fetch until confirmation, then delivers fresh picks instead of pre-import picks', async () => {
  vi.useFakeTimers(); mount(); await upload();
  await act(async () => { vi.advanceTimersByTime(60000); });
  expect(mocks.fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Continue to my recommendations →' }));
  await act(async () => {});
  expect(screen.getByText('Fresh unread match')).toBeTruthy();
  expect(screen.queryByText('Previously read book')).toBeNull();
  expect(mocks.fetch).toHaveBeenCalledWith({ limit: 5 });
  expect(mocks.upload).toHaveBeenCalledTimes(1);
});

it('shows a recoverable error rather than cached preview books after an import', async () => {
  localStorage.setItem('readar_preview_recs', JSON.stringify(stale));
  mocks.fetch.mockRejectedValue(new Error('Offline'));
  mount(); await upload();
  fireEvent.click(screen.getByRole('button', { name: 'Continue to my recommendations →' }));
  expect(await screen.findByText(/We couldn't load your recommendations/)).toBeTruthy();
  expect(screen.queryByText('Previously read book')).toBeNull();
  mocks.fetch.mockResolvedValue(fresh);
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  expect(await screen.findByText('Fresh unread match')).toBeTruthy();
  expect(mocks.upload).toHaveBeenCalledTimes(1);
});

it('retains browser history receipt state when the app remounts, without submitting again', async () => {
  window.history.replaceState(null, '', '/onboarding/import');
  const view = render(<BrowserRouter>{routes()}</BrowserRouter>);
  await upload(); view.unmount();
  // A reload recreates the router from this browser history entry.
  render(<BrowserRouter>{routes()}</BrowserRouter>);
  expect(screen.getByRole('status').textContent).toContain('4 entries saved');
  expect(screen.getByRole('status').textContent).toContain('1 row was skipped');
  expect(mocks.upload).toHaveBeenCalledTimes(1);
  expect(mocks.fetch).not.toHaveBeenCalled();
  window.history.replaceState(null, '', '/');
});
