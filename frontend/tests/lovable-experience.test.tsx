import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import ImportReadingHistoryPage from '../src/pages/ImportReadingHistoryPage';
import ChatMessage from '../src/components/Onboarding/ChatMessage';
import { FinishBook, ReadingReturnCard } from '../src/components/ReadingJourney';
import { safeReturnPath } from '../src/auth/postAuthRedirect';
const mocks = vi.hoisted(() => ({ upload: vi.fn(), finish: vi.fn(), preference: vi.fn() }));
vi.mock('../src/api/client', () => ({ apiClient: { uploadReadingHistoryCsv: mocks.upload, finishReadingBook: mocks.finish,
  saveReadingJourneyPreferences: mocks.preference }, logEvent: vi.fn() }));
function Result() { const location = useLocation(); const navigate = useNavigate(); return <><p>{location.state?.prefetchedRecommendations ? 'Cached picks' : 'Fresh picks'}</p><button onClick={() => navigate(-1)}>Back to receipt</button></>; }
function importPage(state?: object) {
  return render(<StrictMode><MemoryRouter initialEntries={[{ pathname: '/onboarding/import', state }]}><Routes>
    <Route path="/onboarding/import" element={<ImportReadingHistoryPage />} />
    <Route path="/recommendations" element={<Result />} />
  </Routes></MemoryRouter></StrictMode>);
}
function upload() { fireEvent.change(screen.getByLabelText('Goodreads CSV file'), { target: { files: [new File(['Title,Author\nTest,Writer'], 'books.csv', { type: 'text/csv' })] } }); }
async function settle() { await act(async () => {}); }
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks();
  mocks.upload.mockResolvedValue({ imported_count: 4, skipped_count: 2 });
  mocks.finish.mockResolvedValue({ book_id: 'book-1', title: 'Test book', rating: null });
  mocks.preference.mockResolvedValue(undefined);
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
it('waits indefinitely for explicit confirmation before fresh picks, with StrictMode', async () => {
  importPage({ prefetchedRecommendations: ['stale'] }); upload(); await settle();
  expect(screen.getByRole('status').textContent).toContain('4 entries saved');
  expect(screen.getByRole('status').textContent).toContain('2 rows were skipped');
  await act(async () => { vi.advanceTimersByTime(60000); });
  expect(screen.queryByText('Fresh picks')).toBeNull();
  expect(screen.queryByText(/Opening your recommendations shortly/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Continue to my recommendations →' }));
  expect(screen.getByText('Fresh picks')).toBeTruthy();
  expect(mocks.upload).toHaveBeenCalledTimes(1);
});
it('restores the receipt on Back and lets the reader continue again without importing', async () => {
  importPage(); upload(); await settle();
  fireEvent.click(screen.getByText('Continue to my recommendations →'));
  fireEvent.click(screen.getByText('Back to receipt'));
  await act(async () => { vi.advanceTimersByTime(10000); });
  expect(screen.getByRole('heading', { name: 'Your reading history is saved.' })).toBeTruthy();
  fireEvent.click(screen.getByText('Continue to my recommendations →'));
  expect(screen.getByText('Fresh picks')).toBeTruthy();
  expect(mocks.upload).toHaveBeenCalledTimes(1);
});
it('restores a confirmation without uploading again', async () => {
  importPage({ importReceipt: { imported_count: 4, skipped_count: 0 } }); await settle();
  await act(async () => { vi.advanceTimersByTime(60000); });
  expect(screen.getByRole('status').textContent).toContain('4 entries saved');
  expect(mocks.upload).not.toHaveBeenCalled();
  fireEvent.click(screen.getByText('Continue to my recommendations →'));
  expect(screen.getByText('Fresh picks')).toBeTruthy();
});
it('keeps a zero-row import on screen with a retry choice', async () => {
  mocks.upload.mockResolvedValue({ imported_count: 0, skipped_count: 3 });
  importPage(); upload(); await settle();
  await act(async () => { vi.advanceTimersByTime(10000); });
  expect(screen.getByText('No entries were imported.')).toBeTruthy();
  const picker = vi.spyOn(screen.getByLabelText('Goodreads CSV file'), 'click');
  fireEvent.click(screen.getByText('Choose another CSV'));
  expect(picker).toHaveBeenCalledTimes(1);
  mocks.upload.mockResolvedValue({ imported_count: 2, skipped_count: 0 });
  upload(); await settle();
  expect(screen.getByRole('status').textContent).toContain('2 entries saved');
  expect(screen.queryByText('Fresh picks')).toBeNull();
});
it('retains the receipt if another file fails and prevents continuing during its upload', async () => {
  importPage(); upload(); await settle();
  let reject!: (error: Error) => void;
  mocks.upload.mockReturnValueOnce(new Promise((_resolve, r) => { reject = r; }));
  upload(); upload();
  expect(mocks.upload).toHaveBeenCalledTimes(2);
  expect((screen.getByText('Continue to my recommendations →') as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByText('Choose another CSV') as HTMLButtonElement).disabled).toBe(true);
  await act(async () => { reject(new Error('Network unavailable')); });
  expect(screen.getByRole('alert').textContent).toContain('Network unavailable');
  expect(screen.getByRole('status').textContent).toContain('4 entries saved');
  fireEvent.click(screen.getByText('Continue to my recommendations →'));
  expect(screen.getByText('Fresh picks')).toBeTruthy();
});
it('does not replace a saved receipt with an unconfirmed response', async () => {
  importPage({ importReceipt: { imported_count: 4, skipped_count: 0 } });
  mocks.upload.mockResolvedValue({ imported_count: -1, skipped_count: 0 });
  upload(); await settle();
  expect(screen.getByRole('alert').textContent).toContain('could not be confirmed');
  expect(screen.getByRole('status').textContent).toContain('4 entries saved');
});
it('preserves errors and permits retrying the same CSV', async () => {
  mocks.upload.mockRejectedValueOnce(new Error('Network unavailable'));
  importPage(); upload(); await settle();
  expect(screen.getByRole('alert').textContent).toContain('Network unavailable');
  upload(); await settle();
  expect(mocks.upload).toHaveBeenCalledTimes(2);
  expect(screen.getByText('Your reading history is saved.')).toBeTruthy();
});
it('skip keeps already prepared picks', () => {
  importPage({ prefetchedRecommendations: ['ready'] });
  fireEvent.click(screen.getByText('Skip to your picks →'));
  expect(screen.getByText('Cached picks')).toBeTruthy();
});
it('an unmounted upload cannot navigate later', async () => {
  let resolve!: (value: unknown) => void;
  mocks.upload.mockReturnValue(new Promise(r => { resolve = r; }));
  const view = importPage(); upload(); view.unmount();
  await act(async () => { resolve({ imported_count: 3, skipped_count: 0 }); vi.advanceTimersByTime(5000); });
  expect(screen.queryByText('Fresh picks')).toBeNull();
});
const message = { id: 'bot', type: 'bot' as const, content: 'What would help your business next?', timestamp: new Date() };
it('reveals a reply with one complete accessible announcement and skip control', () => {
  const view = render(<ChatMessage message={message} animate />);
  expect(screen.getByRole('status').textContent).toBe(message.content);
  expect(view.container.querySelector('p[aria-hidden="true"]')?.textContent).toBe('');
  act(() => { vi.advanceTimersByTime(120); });
  const partial = view.container.querySelector('p')!.textContent!;
  expect(partial.length).toBeGreaterThan(0); expect(partial.length).toBeLessThan(message.content.length);
  fireEvent.click(screen.getByText('Show full message'));
  expect(screen.getByText(message.content)).toBeTruthy();
  expect(screen.queryByText('Show full message')).toBeNull();
});
it('restored replies and reduced motion show full text immediately', () => {
  const view = render(<ChatMessage message={message} />);
  expect(screen.queryByText('Show full message')).toBeNull(); view.unmount();
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  render(<ChatMessage message={message} animate />);
  expect(screen.getByText(message.content)).toBeTruthy();
  expect(screen.queryByText('Show full message')).toBeNull();
});
function finishForm(saved = vi.fn()) {
  return render(<FinishBook bookId="book-1" title="Test book" challenge="Find customers" tz="UTC" onSaved={saved} onCancel={vi.fn()} onBusyChange={vi.fn()} />);
}
it('finish retry retains notes and request identity until the server confirms', async () => {
  const saved = vi.fn(); mocks.finish.mockRejectedValueOnce(new Error('Lost response'));
  finishForm(saved);
  fireEvent.change(screen.getByLabelText('What changed for you? (optional)'), { target: { value: 'I asked a customer' } });
  fireEvent.click(screen.getByText('Save finished book')); await settle();
  expect(saved).not.toHaveBeenCalled();
  expect((screen.getByLabelText('What changed for you? (optional)') as HTMLTextAreaElement).value).toBe('I asked a customer');
  fireEvent.click(screen.getByText('Save finished book')); await settle();
  expect(saved).toHaveBeenCalledTimes(1);
  expect(mocks.finish.mock.calls[0][1]).toEqual(mocks.finish.mock.calls[1][1]);
  expect(mocks.finish.mock.calls[1][1].rating).toBeNull();
});
it('only changes the challenge when the reader requests it', async () => {
  finishForm(); fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.change(screen.getByLabelText('What would you like help with next?'), { target: { value: 'Hire a team' } });
  fireEvent.click(screen.getByText('Save finished book')); await settle();
  expect(mocks.finish.mock.calls[0][1]).toMatchObject({ next_challenge: 'Hire a team', expected_challenge: 'Find customers' });
});
it('a stale finish requires refresh instead of overwriting newer work', async () => {
  mocks.finish.mockRejectedValue({ response: { status: 409, data: { detail: 'Your challenge changed.' } } });
  finishForm(); fireEvent.click(screen.getByText('Save finished book')); await settle();
  expect((screen.getByText('Save finished book') as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText('Close and refresh Reading')).toBeTruthy();
});
it('snoozes in-app prompts without mutating email preferences', async () => {
  const saved = vi.fn();
  render(<MemoryRouter><ReadingReturnCard tz="UTC" onSaved={saved} journey={{ today: '2026-09-21', show_next_action: true, snoozed_until: null, challenge: '', completions: [], next_action: { kind: 'reading', title: 'Continue reading', detail: 'A book', href: '#reading-book-1', label: 'Continue' } }} /></MemoryRouter>);
  fireEvent.click(screen.getByText('Snooze for a week')); await settle();
  expect(mocks.preference).toHaveBeenCalledWith(true, 7, 'UTC');
  expect(saved).toHaveBeenCalledTimes(1);
});
it.each(['https://example.com', '//example.com', '/\\example.com', '/%2fexample.com', '/%5cexample.com', '/\n/example.com'])('rejects external OAuth return paths: %s', path => {
  expect(safeReturnPath(path)).toBeNull();
});
it('preserves a valid internal OAuth destination', () => {
  expect(safeReturnPath('/reading?book=one#takeaways')).toBe('/reading?book=one#takeaways');
});
