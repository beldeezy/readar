import { useCallback, useRef, useState } from 'react';

/**
 * Thin wrapper around the browser Web Speech API (SpeechRecognition).
 *
 * Exposes a small, engine-agnostic surface so the UI never touches the raw API
 * — and so a server-side transcriber could be swapped in later behind the same
 * shape. `transcript` updates live (interim + final) while recording.
 */
export interface SpeechToText {
  supported: boolean;
  recording: boolean;
  transcript: string;
  start: () => void;
  stop: () => void;
  cancel: () => void;
}

export function useSpeechToText(): SpeechToText {
  const Ctor =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : undefined;
  const supported = !!Ctor;

  const recogRef = useRef<any>(null);
  const finalRef = useRef('');
  const [recording, setRecording] = useState(false);
  const [transcript, setTranscript] = useState('');

  const start = useCallback(() => {
    if (!supported || recogRef.current) return;
    const r = new Ctor();
    r.lang = 'en-US';
    r.continuous = true;
    r.interimResults = true;
    finalRef.current = '';
    setTranscript('');

    r.onresult = (e: any) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const seg = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalRef.current += seg + ' ';
        else interim += seg;
      }
      setTranscript((finalRef.current + interim).replace(/\s+/g, ' ').trim());
    };

    const finish = () => {
      recogRef.current = null;
      setRecording(false);
    };
    r.onerror = finish;
    r.onend = finish;

    try {
      r.start();
      recogRef.current = r;
      setRecording(true);
    } catch {
      recogRef.current = null;
    }
  }, [supported, Ctor]);

  const stop = useCallback(() => {
    const r = recogRef.current;
    if (r) {
      try {
        r.stop();
      } catch {
        /* noop */
      }
    }
    setRecording(false);
  }, []);

  const cancel = useCallback(() => {
    const r = recogRef.current;
    if (r) {
      try {
        r.abort();
      } catch {
        /* noop */
      }
    }
    recogRef.current = null;
    setRecording(false);
    setTranscript('');
  }, []);

  return { supported, recording, transcript, start, stop, cancel };
}
