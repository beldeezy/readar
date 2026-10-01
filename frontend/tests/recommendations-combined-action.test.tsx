import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import RecommendationsPage from '../src/pages/RecommendationsPage';
import BookSelectionNotice from '../src/components/BookSelectionNotice';

const mocks = vi.hoisted(() => ({ fetch: vi.fn(), select: vi.fn() }));
vi.mock('../src/auth/AuthProvider', () => ({ useAuth: () => ({ user: { id: 'fixture-reader' } }) }));
vi.mock('../src/api/client', () => ({
  apiClient: { selectBookForReading: mocks.select }, fetchRecommendations: mocks.fetch,
  logEvent: vi.fn(), logRecommendationClick: vi.fn(), RefreshLimitError: class extends Error {},
}));
vi.mock('../src/services/feedbackApi', () => ({ submitFeedback: vi.fn() }));

// Same title/author and absent metadata as the October 1 screenshot. Even
// without a catalog purchase URL, the combined action offers Amazon search.
const book = { book_id: 'fixture-book', title: 'No B.S. Direct Marketing', author_name: 'Dan S. Kennedy', score: 1 };
const recommendations = { items: [book], request_id: 'fixture-request' };
function Reading() { return <BookSelectionNotice receipt={useLocation().state?.bookSelection} />; }
beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks();
  mocks.fetch.mockReset().mockResolvedValue(recommendations);
  mocks.select.mockReset();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it.each(['fetched', 'prefetched', 'saved-preview'])('uses one save-and-get action on the %s recommendations screen', async source => {
  if (source === 'saved-preview') {
    localStorage.setItem('readar_preview_recs', JSON.stringify([book]));
    mocks.fetch.mockRejectedValue(new Error('Fixture API unavailable'));
  }
  const replace = vi.fn();
  const tab = { opener: {}, document: { body: { textContent: '' } }, location: { replace }, closed: false, close: vi.fn() };
  const open = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window);
  let resolve!: (result: { ok: boolean; status: string }) => void;
  mocks.select.mockReturnValue(new Promise(r => { resolve = r; }));
  render(<MemoryRouter initialEntries={[{ pathname: '/recommendations', state: source === 'prefetched' ? { prefetchedRecommendations: recommendations } : undefined }]}>
    <Routes><Route path="/recommendations" element={<RecommendationsPage />} /><Route path="/reading" element={<Reading />} /></Routes>
  </MemoryRouter>);
  const action = await screen.findByRole('button', { name: 'Get book + add to Reading' });
  expect(screen.queryByRole('button', { name: /^Choose this book$/i })).toBeNull();
  expect(screen.queryByRole('button', { name: /^Get book$/i })).toBeNull();
  fireEvent.click(action);
  expect(mocks.select).toHaveBeenCalledTimes(1);
  expect(mocks.select.mock.calls[0][0]).toMatchObject({ book_id: book.book_id, intent: 'get_book' });
  expect(open).toHaveBeenCalledTimes(1);
  expect(replace).not.toHaveBeenCalled();
  await act(async () => resolve({ ok: true, status: 'waiting_for_book' }));
  expect(replace).toHaveBeenCalledWith('https://www.amazon.com/s?k=No%20B.S.%20Direct%20Marketing%20Dan%20S.%20Kennedy');
  expect(screen.getByRole('status').textContent).toContain('is saved to Reading');
});
