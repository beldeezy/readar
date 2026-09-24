import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import ChooseBookButton from '../src/components/ChooseBookButton';
import BookSelectionNotice from '../src/components/BookSelectionNotice';
import RecommendationCard from '../src/components/RecommendationCard';
import BookDetailPage from '../src/pages/BookDetailPage';
import { amazonBookUrl } from '../src/utils/amazonBookUrl';

const mocks = vi.hoisted(() => ({ select: vi.fn(), getBook: vi.fn(), status: vi.fn() }));
vi.mock('../src/api/client', () => ({ apiClient: { selectBookForReading: mocks.select, getBook: mocks.getBook, setBookStatus: mocks.status }, logRecommendationClick: vi.fn() }));
vi.mock('../src/services/feedbackApi', () => ({ submitFeedback: vi.fn() }));
const amazon = 'https://www.amazon.com/dp/1234567890?tag=readar-20';
const book = { id: 'book-1', book_id: 'book-1', title: 'Steady Leads', author_name: 'Test Author', purchase_url: amazon, score: 1, relevancy_score: 1 };
const saved = { ok: true, status: 'waiting_for_book' };
let tab: { opener: unknown; document: { title: string; body: { textContent: string } }; location: { replace: ReturnType<typeof vi.fn> }; close: ReturnType<typeof vi.fn>; closed: boolean };
let open: ReturnType<typeof vi.spyOn>;
function Hub() { const location = useLocation(); const navigate = useNavigate(); return <><BookSelectionNotice receipt={location.state?.bookSelection} /><button onClick={() => navigate(-1)}>Back</button></>; }
function mount(element = <ChooseBookButton bookId={book.id} title={book.title} author={book.author_name} purchaseUrl={amazon} requestId="req-1" position={0} />) {
  return render(<StrictMode><MemoryRouter initialEntries={['/book/book-1']}><Routes>
    <Route path="/book/:id" element={element} /><Route path="/reading" element={<Hub />} />
  </Routes></MemoryRouter></StrictMode>);
}
async function settle() { await act(async () => {}); }
const clickGet = () => fireEvent.click(screen.getByRole('button', { name: 'Get book + add to Reading' }));
beforeEach(() => {
  vi.clearAllMocks();
  mocks.select.mockReset().mockResolvedValue(saved);
  mocks.getBook.mockReset().mockResolvedValue(book);
  tab = { opener: {}, document: { title: '', body: { textContent: '' } }, location: { replace: vi.fn() }, close: vi.fn(), closed: false };
  open = vi.spyOn(window, 'open').mockReturnValue(tab as unknown as Window);
});
afterEach(() => cleanup());

it('saves once before visiting Amazon and sends the reader to the Reading receipt', async () => {
  let resolve!: (data: typeof saved) => void;
  mocks.select.mockReturnValueOnce(new Promise(r => { resolve = r; }));
  mount(); clickGet();
  fireEvent.click(screen.getByRole('button', { name: 'Saving your choice…' }));
  expect(open).toHaveBeenCalledTimes(1);
  expect(open).toHaveBeenCalledWith('about:blank', '_blank');
  expect(tab.opener).toBeNull();
  expect(tab.location.replace).not.toHaveBeenCalled();
  expect(mocks.select).toHaveBeenCalledTimes(1);
  expect(mocks.select).toHaveBeenCalledWith({ book_id: 'book-1', request_id: 'req-1', position: 0, intent: 'get_book' });
  expect((screen.getByRole('button', { name: 'I already have this book' }) as HTMLButtonElement).disabled).toBe(true);
  await act(async () => resolve(saved));
  expect(tab.location.replace).toHaveBeenCalledWith(amazon);
  expect(tab.close).not.toHaveBeenCalled();
  expect(screen.getByRole('status').textContent).toContain('Steady Leads is saved to Reading');
  expect(screen.getByRole('status').textContent).toContain('Select Start reading when your copy is ready');
  expect(screen.getByRole('link', { name: 'Open Amazon ↗' }).getAttribute('href')).toBe(amazon);
});

it.each(['blocked', 'closed', 'denied'] as const)('keeps the saved choice and a direct link when the tab is %s', async mode => {
  if (mode === 'blocked') open.mockReturnValue(null);
  if (mode === 'closed') tab.closed = true;
  if (mode === 'denied') tab.location.replace.mockImplementation(() => { throw new Error('navigation denied'); });
  mount(); clickGet(); await settle();
  expect(screen.getByRole('status').textContent).toContain('Your choice is still saved');
  const link = screen.getByRole('link', { name: 'Open Amazon ↗' });
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  expect(link.getAttribute('href')).toBe(amazon);
  expect(mocks.select).toHaveBeenCalledTimes(1);
});

it('closes the reserved tab on save failure and lets the user retry the same selection', async () => {
  mocks.select.mockRejectedValueOnce(new Error('database failure'));
  mount(); clickGet(); await settle();
  expect(tab.close).toHaveBeenCalledTimes(1);
  expect(tab.location.replace).not.toHaveBeenCalled();
  expect(screen.getByRole('alert').textContent).toContain("couldn't confirm your saved choice");
  clickGet(); await settle();
  expect(mocks.select.mock.calls[1]).toEqual(mocks.select.mock.calls[0]);
  expect(screen.getByRole('status').textContent).toContain('Steady Leads is saved');
});

it.each([{}, { ok: false, status: 'waiting_for_book' }, { ok: true, status: 'interested' }])('does not open Amazon for an unconfirmed response %j', async data => {
  mocks.select.mockResolvedValueOnce(data);
  mount(); clickGet(); await settle();
  expect(tab.location.replace).not.toHaveBeenCalled();
  expect(tab.close).toHaveBeenCalled();
  expect(screen.getByRole('alert')).toBeTruthy();
});

it('retains the already-owned path without opening Amazon or starting reading', async () => {
  mocks.select.mockResolvedValueOnce({ ok: true, status: 'reading_next' });
  mount(); fireEvent.click(screen.getByRole('button', { name: 'I already have this book' })); await settle();
  expect(open).not.toHaveBeenCalled();
  expect(mocks.select.mock.calls[0][0].intent).toBe('choose');
  expect(mocks.status).not.toHaveBeenCalled();
  expect(screen.getByRole('status').textContent).toContain('Select Start reading when you’re ready');
  expect(screen.queryByRole('link', { name: 'Open Amazon ↗' })).toBeNull();
});

it('preserves a started book when it is selected again after Back', async () => {
  mocks.select.mockResolvedValue({ ok: true, status: 'currently_reading' });
  mount(); clickGet(); await settle();
  expect(screen.getByText('Your existing reading progress is unchanged.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Back' })); clickGet(); await settle();
  expect(screen.getByText('Your existing reading progress is unchanged.')).toBeTruthy();
  expect(mocks.status).not.toHaveBeenCalled();
});

it('closes an abandoned blank tab and cannot redirect after unmount', async () => {
  let resolve!: (data: typeof saved) => void;
  mocks.select.mockReturnValueOnce(new Promise(r => { resolve = r; }));
  const view = mount(); clickGet(); view.unmount();
  expect(tab.close).toHaveBeenCalled();
  await act(async () => resolve(saved));
  expect(tab.location.replace).not.toHaveBeenCalled();
});

it('still saves when book data contains neither a usable URL nor a title', async () => {
  mocks.select.mockResolvedValueOnce({ ok: true, status: 'reading_next' });
  mount(<ChooseBookButton bookId="book-1" />);
  fireEvent.click(screen.getByRole('button', { name: 'Add to Reading' })); await settle();
  expect(open).not.toHaveBeenCalled();
  expect(screen.getByRole('status').textContent).toContain('Your book is saved');
});

it('renders one combined primary action on the actual recommendation card', async () => {
  mount(<RecommendationCard book={book} onAction={vi.fn()} />);
  expect(screen.queryByRole('button', { name: 'Choose this book' })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Get Book' })).toBeNull();
  clickGet(); await settle();
  expect(tab.location.replace).toHaveBeenCalledWith(amazon);
});

it('uses the same combined action on book details', async () => {
  mount(<BookDetailPage />); await settle();
  expect(screen.queryByRole('button', { name: 'Start reading' })).toBeNull();
  clickGet(); await settle();
  expect(mocks.select.mock.calls[0][0].intent).toBe('get_book');
  expect(tab.location.replace).toHaveBeenCalledWith(amazon);
});

it('keeps affiliate URLs and safely falls back to an Amazon title search', () => {
  expect(amazonBookUrl(amazon, book.title)).toBe(amazon);
  const fallback = 'https://www.amazon.com/s?k=Steady%20Leads%20Test%20Author';
  for (const invalid of [undefined, 'javascript:alert(1)', 'https://amazon.com.evil.test/book', 'https://bookshop.org/book']) {
    expect(amazonBookUrl(invalid, book.title, book.author_name)).toBe(fallback);
  }
  expect(amazonBookUrl('javascript:alert(1)')).toBeNull();
});
