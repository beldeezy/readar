import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import RecommendationCard from '../src/components/RecommendationCard';
import ReadingPage from '../src/pages/ReadingPage';
const mocks = vi.hoisted(() => ({ select: vi.fn(), list: vi.fn(), status: vi.fn(), remove: vi.fn(), search: vi.fn(), journey: vi.fn() }));
vi.mock('../src/api/client', () => ({ apiClient: { selectBookForReading: mocks.select, getBookStatusList: mocks.list, setBookStatus: mocks.status, deleteBookStatus: mocks.remove, getBooks: mocks.search, getReadingJourney: mocks.journey }, logRecommendationClick: vi.fn() }));
vi.mock('../src/services/feedbackApi', () => ({ submitFeedback: vi.fn() }));
vi.mock('../src/components/BookReadingProgress', () => ({ default: () => <p>Reading progress controls</p> }));
vi.mock('../src/components/ReadingRewards', () => ({ default: () => null }));
vi.mock('../src/components/FriendlyCompetition', () => ({ default: () => null }));
vi.mock('../src/components/ReadingTakeaways', () => ({ default: () => null }));
const book = { id: 'book-1', book_id: 'book-1', title: 'Scientific Advertising', author_name: 'Claude C. Hopkins', score: 1, relevancy_score: 1 };
let savedStatus: string | null;
function mount(path = '/recommendations') {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/recommendations" element={<RecommendationCard book={book} onAction={vi.fn()} />} />
    <Route path="/reading" element={<ReadingPage />} />
  </Routes></MemoryRouter>);
}
const start = () => screen.getByRole('button', { name: 'Start reading', exact: true });
const bookRow = () => screen.getByRole('heading', { name: book.title }).closest('li')!;
beforeEach(() => {
  vi.clearAllMocks(); savedStatus = null;
  mocks.list.mockReset().mockImplementation(async () => savedStatus ? [{ ...book, status: savedStatus }] : []);
  mocks.select.mockReset().mockImplementation(async ({ intent }) => {
    savedStatus = savedStatus || (intent === 'get_book' ? 'waiting_for_book' : 'reading_next');
    return { ok: true, status: savedStatus };
  });
  mocks.status.mockReset().mockImplementation(async ({ status }) => { savedStatus = status; return { ok: true }; });
  mocks.remove.mockReset().mockImplementation(async () => { savedStatus = null; return { ok: true }; });
  mocks.search.mockReset().mockResolvedValue([book]);
  mocks.journey.mockResolvedValue({ today: '2026-09-24', challenge: '', show_next_action: true, snoozed_until: null, next_action: null, completions: [] });
  vi.spyOn(window, 'open').mockReturnValue(null);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('moves a recommendation into Reading, retains it on remount, and starts only explicitly', async () => {
  let view = mount();
  fireEvent.click(screen.getByRole('button', { name: 'Get book + add to Reading' }));
  await screen.findByRole('heading', { name: book.title });
  expect(within(bookRow()).getByText('Waiting for my copy')).toBeTruthy();
  expect(screen.getByRole('link', { name: 'Open Amazon ↗' })).toBeTruthy();
  expect(mocks.status).not.toHaveBeenCalled();
  view.unmount(); view = mount('/reading');
  await screen.findByRole('heading', { name: book.title });
  expect(within(bookRow()).getByText('Waiting for my copy')).toBeTruthy();
  fireEvent.click(start()); await screen.findByText('Reading progress controls');
  expect(savedStatus).toBe('currently_reading');
  view.unmount(); view = mount('/reading'); await screen.findByText('Reading progress controls');
  fireEvent.click(screen.getByRole('button', { name: 'Move to Up next' }));
  await screen.findByRole('button', { name: 'Start reading', exact: true });
  expect(savedStatus).toBe('reading_next');
  expect(screen.getAllByRole('heading', { name: book.title })).toHaveLength(1);
});
it('the already-owned path opens Reading without a purchase tab or automatic start', async () => {
  mount(); fireEvent.click(screen.getByRole('button', { name: 'I already have this book' }));
  await screen.findByRole('heading', { name: book.title });
  expect(window.open).not.toHaveBeenCalled(); expect(savedStatus).toBe('reading_next');
  expect(start()).toBeTruthy(); expect(mocks.status).not.toHaveBeenCalled();
});
it.each([{}, { ok: false }])('retains the waiting book when a start or removal is unconfirmed: %j', async response => {
  savedStatus = 'waiting_for_book'; mocks.status.mockResolvedValue(response); mocks.remove.mockResolvedValue(response);
  mount('/reading'); await screen.findByRole('heading', { name: book.title });
  fireEvent.click(start()); expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.queryByText('Reading progress controls')).toBeNull();
  expect(within(bookRow()).getByText('Waiting for my copy')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: `Remove ${book.title} from reading list` })); await act(async () => {});
  expect(within(bookRow()).getByText('Waiting for my copy')).toBeTruthy();
  expect(screen.queryByText(`${book.title} was removed from your reading list.`)).toBeNull();
});
it('keeps a failed start retryable without moving the book early', async () => {
  savedStatus = 'waiting_for_book'; mocks.status.mockRejectedValueOnce(new Error('Offline'));
  mount('/reading'); await screen.findByRole('heading', { name: book.title });
  fireEvent.click(start()); await screen.findByRole('alert'); expect(savedStatus).toBe('waiting_for_book');
  fireEvent.click(start()); await screen.findByText('Reading progress controls'); expect(mocks.status).toHaveBeenCalledTimes(2);
});
it('recovers the saved list after a load failure', async () => {
  savedStatus = 'waiting_for_book'; mocks.list.mockRejectedValueOnce(new Error('Offline'));
  mount('/reading'); await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
  await screen.findByRole('heading', { name: book.title });
});
it.each([{}, { ok: false, status: 'reading_next' }, { ok: true, status: 'interested' }])('search does not announce an unconfirmed selection: %j', async response => {
  mocks.select.mockResolvedValue(response); mount('/reading');
  const search = await screen.findByRole('textbox', { name: 'Choose a book' }); await act(async () => {});
  fireEvent.change(search, { target: { value: 'Scientific' } });
  fireEvent.click(await screen.findByRole('button', { name: /Scientific Advertising.*Choose this book/ }));
  await screen.findByRole('alert');
  expect(screen.queryByText(`${book.title} is saved to your reading list.`)).toBeNull();
  expect(screen.queryByRole('heading', { name: book.title })).toBeNull();
});
