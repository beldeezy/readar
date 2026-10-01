import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ChatOnboardingPage from '../src/pages/ChatOnboardingPage';

const mocks = vi.hoisted(() => ({ chat: vi.fn(), extract: vi.fn() }));
vi.mock('../src/api/client', () => ({ apiClient: { nepqChat: mocks.chat, nepqExtract: mocks.extract }, logEvent: vi.fn() }));
vi.mock('../src/hooks/useSpeechToText', () => ({ useSpeechToText: () => ({ recording: false, supported: false }) }));
const question = "Does that capture what you want from your next book, or would you change anything?";
const summary = `You want practical examples to generate consistent cleaning leads.\n\n${question}`;
const handoff = 'Thanks for confirming. Select ‘Take me to my recommendations’ below when you’re ready to see your matches.';
const turn = (message = summary, done = false) => ({ message, stage_index: 6, stage_key: 'transition', turns_in_stage: 1, done, ui: done ? null : 'confirm' });
const profile = { business_stage: 'early-revenue', business_model: 'service', biggest_challenge: 'Consistent cleaning leads', ideal_book_description: 'Practical examples' };
const progressKey = 'readar_onboarding_progress';
function page() {
  return render(<StrictMode><MemoryRouter initialEntries={['/onboarding']}><Routes>
    <Route path="/onboarding" element={<ChatOnboardingPage />} />
    <Route path="/recommendations/loading" element={<p>Preparing your books</p>} />
  </Routes></MemoryRouter></StrictMode>);
}
async function settle() { await act(async () => {}); }
function reply(value: string) {
  fireEvent.change(screen.getByRole('textbox', { name: 'Your reply' }), { target: { value } });
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
}
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear();
  mocks.chat.mockReset().mockResolvedValue(turn());
  mocks.extract.mockReset().mockResolvedValue(profile);
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('offers confirmation and an explicit correction path without discarding a draft', async () => {
  page(); await settle();
  expect(mocks.chat).toHaveBeenCalledTimes(1); // StrictMode cannot duplicate the opener.
  const textbox = screen.getByRole('textbox', { name: 'Your reply' }) as HTMLTextAreaElement;
  fireEvent.change(textbox, { target: { value: 'Actually, profit margins are the priority.' } });
  fireEvent.click(screen.getByRole('button', { name: "I'd like to change something" }));
  expect(document.activeElement).toBe(textbox);
  expect(textbox.value).toBe('Actually, profit margins are the priority.');
  expect(mocks.chat).toHaveBeenCalledTimes(1);
  mocks.chat.mockResolvedValueOnce(turn(`You want practical help improving cleaning margins.\n\n${question}`));
  fireEvent.click(screen.getByRole('button', { name: 'Send' })); await settle();
  expect(mocks.chat.mock.calls[1][0]).toEqual([
    { role: 'assistant', content: summary },
    { role: 'user', content: 'Actually, profit margins are the priority.' },
  ]);
  expect(screen.getByRole('button', { name: "Yes, that's right" })).toBeTruthy();
  expect(screen.queryByRole('button', { name: /Take me to my recommendations/ })).toBeNull();
  expect(mocks.extract).not.toHaveBeenCalled();
});

it('waits for explicit confirmation, then an explicit handoff, retaining the full profile', async () => {
  page(); await settle();
  expect(mocks.extract).not.toHaveBeenCalled();
  mocks.chat.mockResolvedValueOnce(turn(handoff, true));
  fireEvent.click(screen.getByRole('button', { name: "Yes, that's right" })); await settle();
  expect(screen.getByText(handoff)).toBeTruthy();
  expect(screen.queryByRole('textbox')).toBeNull();
  expect(mocks.extract).not.toHaveBeenCalled();
  const history = JSON.parse(localStorage.getItem(progressKey)!).history;
  fireEvent.click(screen.getByRole('button', { name: /Take me to my recommendations/ })); await settle();
  expect(mocks.extract).toHaveBeenCalledWith(history);
  expect(history.at(-2)).toEqual({ role: 'user', content: "Yes, that's right" });
  expect(screen.getByText('Preparing your books')).toBeTruthy();
  expect(JSON.parse(localStorage.getItem('readar_pending_onboarding')!)).toEqual({ full_name: '', ...profile });
  expect(JSON.parse(localStorage.getItem('readar_onboarding_answers')!)).toEqual(profile);
  expect(localStorage.getItem(progressKey)).toBeNull();
});

it('retries the same correction after an error without duplicating the answer', async () => {
  page(); await settle();
  mocks.chat.mockRejectedValueOnce(new Error('question repair unavailable'));
  reply('Yes, but I need help with margins first.'); await settle();
  const failedRequest = mocks.chat.mock.calls[1];
  expect(screen.getByRole('alert').textContent).toContain('Your answers are still here');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' })); await settle();
  expect(mocks.chat.mock.calls[2]).toEqual(failedRequest);
  const saved = JSON.parse(localStorage.getItem(progressKey)!);
  expect(saved.history.filter((m: { role: string }) => m.role === 'user')).toHaveLength(1);
  expect(mocks.extract).not.toHaveBeenCalled();
});

it('restores summary confirmation on refresh without replaying the model', async () => {
  const view = page(); await settle(); view.unmount(); mocks.chat.mockClear();
  page(); await settle();
  expect(screen.getByRole('button', { name: "Yes, that's right" })).toBeTruthy();
  expect(screen.getByRole('button', { name: "I'd like to change something" })).toBeTruthy();
  expect(mocks.chat).not.toHaveBeenCalled();
});

it('recovers an interrupted correction on refresh using its saved transcript', async () => {
  const view = page(); await settle();
  mocks.chat.mockReturnValueOnce(new Promise(() => {}));
  reply('Please focus on margins.'); await settle();
  const sent = mocks.chat.mock.calls[1];
  view.unmount(); page(); await settle();
  expect(mocks.chat.mock.calls[2]).toEqual(sent);
  expect(screen.getByRole('button', { name: "Yes, that's right" })).toBeTruthy();
});

it('retains confirmed answers if profile extraction fails and allows retry', async () => {
  page(); await settle();
  mocks.chat.mockResolvedValueOnce(turn(handoff, true));
  fireEvent.click(screen.getByRole('button', { name: "Yes, that's right" })); await settle();
  mocks.extract.mockRejectedValueOnce(new Error('temporary outage'));
  fireEvent.click(screen.getByRole('button', { name: /Take me to my recommendations/ })); await settle();
  const history = JSON.parse(localStorage.getItem(progressKey)!).history;
  expect(screen.getByRole('alert').textContent).toContain('Your answers are still here');
  fireEvent.click(screen.getByRole('button', { name: 'Try again' })); await settle();
  expect(mocks.extract.mock.calls).toEqual([[history], [history]]);
  expect(screen.getByText('Preparing your books')).toBeTruthy();
});

it.each(['keyboard', 'button'])('keeps the desktop composer active after %s submission without sending a draft twice', async mode => {
  page(); await settle();
  const textbox = screen.getByRole('textbox', { name: 'Your reply' }) as HTMLTextAreaElement;
  textbox.focus();
  fireEvent.change(textbox, { target: { value: 'Please focus on margins.' } });
  let resolve!: (value: ReturnType<typeof turn>) => void;
  mocks.chat.mockReturnValueOnce(new Promise(r => { resolve = r; }));
  if (mode === 'keyboard') fireEvent.keyDown(textbox, { key: 'Enter' });
  else {
    const send = screen.getByRole('button', { name: 'Send' });
    send.focus(); // fireEvent.click alone does not simulate browser focus movement.
    fireEvent.click(send);
  }
  expect(textbox.disabled).toBe(false);
  expect(document.activeElement).toBe(textbox);
  fireEvent.change(textbox, { target: { value: 'My next thought' } });
  fireEvent.keyDown(textbox, { key: 'Enter' });
  expect(mocks.chat).toHaveBeenCalledTimes(2);
  await act(async () => resolve(turn()));
  expect(document.activeElement).toBe(textbox);
  expect(textbox.value).toBe('My next thought');
  expect((screen.getByRole('button', { name: 'Send' }) as HTMLButtonElement).disabled).toBe(false);
});

it('does not steal focus when a reply arrives and preserves the next draft on failure/retry', async () => {
  page(); await settle();
  const textbox = screen.getByRole('textbox', { name: 'Your reply' }) as HTMLTextAreaElement;
  let reject!: (error: Error) => void;
  mocks.chat.mockReturnValueOnce(new Promise((_, r) => { reject = r; }));
  reply('Focus on margins.');
  fireEvent.change(textbox, { target: { value: 'Draft to send next' } });
  await act(async () => reject(new Error('Temporary failure')));
  expect(textbox.value).toBe('Draft to send next');
  const retry = screen.getByRole('button', { name: 'Try again' });
  retry.focus();
  fireEvent.click(retry); await settle();
  expect(textbox.value).toBe('Draft to send next');
  expect(document.activeElement).not.toBe(textbox);
});

it('does not programmatically reopen a touch keyboard after clicking Send', async () => {
  vi.mocked(window.matchMedia).mockImplementation(query => ({ matches: query.includes('prefers-reduced-motion'), addEventListener: vi.fn(), removeEventListener: vi.fn() }) as any);
  page(); await settle();
  const textbox = screen.getByRole('textbox', { name: 'Your reply' });
  fireEvent.change(textbox, { target: { value: 'Focus on margins.' } });
  const send = screen.getByRole('button', { name: 'Send' });
  send.focus(); fireEvent.click(send); await settle();
  expect(document.activeElement).not.toBe(textbox);
});
