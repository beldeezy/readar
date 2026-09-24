import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReadingPage from '../src/pages/ReadingPage';
const mocks = vi.hoisted(() => ({ list: vi.fn(), journey: vi.fn(), finish: vi.fn(), status: vi.fn() }));
vi.mock('../src/api/client', () => ({ apiClient: { getBookStatusList: mocks.list, getReadingJourney: mocks.journey,
  finishReadingBook: mocks.finish, setBookStatus: mocks.status } }));
vi.mock('../src/components/BookReadingProgress', () => ({ default: () => <p>Saved reading progress</p> }));
vi.mock('../src/components/ReadingRewards', () => ({ default: () => <p>Saved rewards</p> }));
vi.mock('../src/components/FriendlyCompetition', () => ({ default: () => <p>Competition</p> }));
vi.mock('../src/components/ReadingTakeaways', () => ({ default: () => <p id="reading-takeaways">My takeaways</p> }));
const completed = { book_id: 'book-1', title: 'The Mom Test', completed_on: '2026-09-21', rating: null, reflection: '', challenge_before: 'Find customers', challenge_after: 'Find customers' };
const journey = { today: '2026-09-21', challenge: 'Find customers', show_next_action: true, snoozed_until: null, next_action: null, completions: [] as any[] };
function mount() { return render(<MemoryRouter><Routes><Route path="/" element={<ReadingPage />} /><Route path="/recommendations" element={<p>Fresh next-book picks</p>} /></Routes></MemoryRouter>); }
beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([{ book_id: 'book-1', title: 'The Mom Test', status: 'currently_reading', updated_at: '2026-09-21' }]);
  mocks.journey.mockResolvedValue(journey);
  mocks.finish.mockImplementation(async () => { mocks.journey.mockResolvedValue({ ...journey, completions: [completed] }); return completed; });
  mocks.status.mockResolvedValue({ ok: true });
});
afterEach(cleanup);
it('finishes from the actual Reading page, refreshes saved completions and continues to new picks', async () => {
  mount();
  fireEvent.click(await screen.findByText('Finish book'));
  fireEvent.click(screen.getByText('Save finished book'));
  expect(await screen.findByText('You finished The Mom Test.')).toBeTruthy();
  expect(await screen.findByText('Recently finished')).toBeTruthy();
  expect(screen.queryByText('Finish book')).toBeNull();
  fireEvent.click(screen.getAllByText('Find my next book →')[0]);
  expect(await screen.findByText('Fresh next-book picks')).toBeTruthy();
});
it('a failed finish keeps the form and active book available', async () => {
  mocks.finish.mockRejectedValue(new Error('Unavailable'));
  mount(); fireEvent.click(await screen.findByText('Finish book'));
  fireEvent.click(screen.getByText('Save finished book'));
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(screen.getByText('Saved reading progress')).toBeTruthy();
  expect(screen.queryByText('Recently finished')).toBeNull();
  fireEvent.click(screen.getByText('Keep reading'));
  await waitFor(() => expect((screen.getByText('Finish book') as HTMLButtonElement).disabled).toBe(false));
});
it('refreshes the return prompt when a saved book is started', async () => {
  mocks.list.mockResolvedValue([{ book_id: 'book-1', title: 'The Mom Test', status: 'reading_next' }]);
  mount(); fireEvent.click(await screen.findByText('Start reading'));
  await waitFor(() => expect(mocks.journey).toHaveBeenCalledTimes(2));
  expect(screen.getByText('Saved reading progress')).toBeTruthy();
});
