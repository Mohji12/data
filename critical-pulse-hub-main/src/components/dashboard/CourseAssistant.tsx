import { FormEvent, useEffect, useRef, useState } from 'react';
import { MessageCircle, Mic, Send, X } from 'lucide-react';
import { apiClient } from '@/lib/apiClient';

type SpeechResult = { isFinal: boolean; 0: { transcript: string } };
type SpeechRecEvent = { resultIndex: number; results: ArrayLike<SpeechResult> };
type SpeechRec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

function createRecognizer(): SpeechRec | null {
  if (typeof window === 'undefined') return null;
  const host = window as Window & {
    SpeechRecognition?: new () => SpeechRec;
    webkitSpeechRecognition?: new () => SpeechRec;
  };
  const Ctor = host.SpeechRecognition || host.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

let liveUtterance: SpeechSynthesisUtterance | null = null;
let queuedSpeech = '';
let speechArmed = false;

function speakNow(text: string) {
  const synth = window.speechSynthesis;
  if (!synth) return;
  const plain = text.replace(/\s+/g, ' ').trim();
  if (!plain) return;
  const utterance = new SpeechSynthesisUtterance(plain);
  liveUtterance = utterance;
  utterance.lang = 'en-IN';
  utterance.rate = 1;
  const voices = synth.getVoices();
  const voice =
    voices.find((item) => /en-IN/i.test(item.lang)) ||
    voices.find((item) => /^en/i.test(item.lang));
  if (voice) utterance.voice = voice;
  if (synth.paused) synth.resume();
  synth.speak(utterance);
}

/** iPhone and Chrome drop speech that starts after a network call. Arm it inside the tap. */
function armSpeech() {
  const synth = window.speechSynthesis;
  if (!synth || speechArmed) return;
  speechArmed = true;
  synth.getVoices();
  const kick = () => {
    if (!speechArmed) return;
    if (queuedSpeech) {
      const next = queuedSpeech;
      queuedSpeech = '';
      speechArmed = false;
      speakNow(next);
      return;
    }
    const silent = new SpeechSynthesisUtterance(' ');
    silent.volume = 0.01;
    silent.onend = () => kick();
    liveUtterance = silent;
    synth.speak(silent);
  };
  kick();
}

function speakReply(text: string) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return;
  queuedSpeech = text;
  if (!speechArmed) {
    const synth = window.speechSynthesis;
    const start = () => {
      queuedSpeech = '';
      speakNow(text);
    };
    if (synth.getVoices().length === 0) {
      synth.addEventListener('voiceschanged', start, { once: true });
      synth.getVoices();
      window.setTimeout(start, 250);
    } else {
      window.setTimeout(start, 60);
    }
    return;
  }
}

function stopSpeech() {
  speechArmed = false;
  queuedSpeech = '';
  liveUtterance = null;
  window.speechSynthesis?.cancel();
}

type ChatMessage = { role: 'user' | 'assistant'; text: string };

const STARTER =
  'Ask about your course, watch progress, or mock-test scores. Answers come only from your account after login.';

const STARTER_SUGGESTIONS = [
  'Show my batch hierarchy',
  'What packages are in my batch?',
  'What is my watch progress?',
  'When does my access end?',
];

type CourseAssistantProps = {
  endpoint?: string;
  title?: string;
  subtitle?: string;
  starter?: string;
  suggestions?: string[];
};

export default function CourseAssistant({
  endpoint = '/dashboard/assistant',
  title = 'Course assistant',
  subtitle = 'Your account data only',
  starter = STARTER,
  suggestions: initialSuggestions = STARTER_SUGGESTIONS,
}: CourseAssistantProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>(initialSuggestions);
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'assistant', text: starter }]);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRec | null>(null);
  const listeningRef = useRef(false);
  const spokenRef = useRef('');
  const sendRef = useRef<(text: string, options?: { speak?: boolean }) => void>(() => {});
  const requestRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      listeningRef.current = false;
      recognitionRef.current?.stop();
      abortRef.current?.abort();
      stopSpeech();
    };
  }, []);

  const send = async (text: string, options?: { speak?: boolean }) => {
    const message = text.trim();
    if (!message) return;
    abortRef.current?.abort();
    stopSpeech();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    if (options?.speak !== false) armSpeech();
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setDraft('');
    setPending(true);
    try {
      const data = (await apiClient(endpoint, {
        method: 'POST',
        body: JSON.stringify({ message }),
        signal: controller.signal,
      })) as { reply?: string; suggestions?: string[] };
      if (requestId !== requestRef.current) return;
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: data.reply || 'I could not read your account just now.' },
      ]);
      if (Array.isArray(data.suggestions) && data.suggestions.length) {
        setSuggestions(data.suggestions);
      }
      if (data.reply) speakReply(data.reply);
    } catch (err) {
      if (controller.signal.aborted || requestId !== requestRef.current) return;
      const detail = err instanceof Error ? err.message : 'Could not reach your account data.';
      setMessages((prev) => [...prev, { role: 'assistant', text: detail }]);
    } finally {
      if (requestId === requestRef.current) setPending(false);
    }
  };

  sendRef.current = send;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  const finishListening = () => {
    listeningRef.current = false;
    setListening(false);
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    try {
      recognition?.stop();
    } catch {
      /* already stopped */
    }
    const spoken = spokenRef.current.trim();
    spokenRef.current = '';
    if (spoken) sendRef.current(spoken, { speak: true });
  };

  const toggleMic = () => {
    if (listeningRef.current) {
      finishListening();
      return;
    }
    const recognition = createRecognizer();
    if (!recognition) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: 'This browser cannot turn speech into text. Type your question, or open the dashboard in Chrome or Safari.',
        },
      ]);
      return;
    }

    spokenRef.current = '';
    recognition.lang = 'en-IN';
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let next = '';
      for (let i = 0; i < event.results.length; i += 1) {
        next += event.results[i][0]?.transcript || '';
      }
      const text = next.trim().slice(0, 500);
      spokenRef.current = text;
      setDraft(text);
    };
    recognition.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      listeningRef.current = false;
      setListening(false);
      recognitionRef.current = null;
      const text =
        event.error === 'not-allowed'
          ? 'Microphone permission is blocked. Allow the mic for this site, then tap it again.'
          : event.error === 'language-not-supported'
            ? 'English speech recognition is not available in this browser.'
            : 'The microphone could not hear a question. Tap it and speak again.';
      setMessages((prev) => [...prev, { role: 'assistant', text }]);
    };
    recognition.onend = () => {
      // Chrome ends the session on a short pause. Keep listening until the user taps stop.
      if (!listeningRef.current || recognitionRef.current !== recognition) return;
      try {
        recognition.start();
      } catch {
        /* start while already running */
      }
    };
    recognitionRef.current = recognition;
    listeningRef.current = true;
    setListening(true);
    setDraft('');
    try {
      recognition.start();
    } catch {
      listeningRef.current = false;
      setListening(false);
      recognitionRef.current = null;
    }
  };

  return (
    <div className="fixed bottom-20 right-3 z-40 flex flex-col items-end lg:bottom-6 lg:right-6">
      {open && (
        <div className="mb-3 flex h-[min(70vh,520px)] w-[min(100vw-1.5rem,380px)] flex-col overflow-hidden rounded-sm border border-border-soft bg-chalk shadow-lg">
          <div className="flex items-center justify-between border-b border-border-soft px-4 py-3">
            <div>
              <p className="font-display text-base font-bold text-slate">{title}</p>
              <p className="font-mono text-[10px] uppercase tracking-wide text-ink-faint">{subtitle}</p>
            </div>
            <button
              type="button"
              className="rounded-sm p-1 text-ink-muted hover:bg-chalk-warm"
              onClick={() => {
                listeningRef.current = false;
                recognitionRef.current?.stop();
                recognitionRef.current = null;
                stopSpeech();
                setListening(false);
                setOpen(false);
              }}
              aria-label="Close assistant"
            >
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {messages.map((item, index) => (
              <div
                key={`${item.role}-${index}`}
                className={`max-w-[95%] whitespace-pre-wrap rounded-sm px-3 py-2 font-sans text-sm ${
                  item.role === 'user'
                    ? 'ml-auto bg-slate text-chalk'
                    : 'bg-chalk-warm text-ink'
                }`}
              >
                {item.text}
              </div>
            ))}
            {listening && (
              <p className="font-mono text-[11px] text-mint">Listening... tap the microphone again to send.</p>
            )}
            {pending && <p className="font-mono text-[11px] text-ink-faint">Looking up your records...</p>}
          </div>
          <div className="flex gap-2 overflow-x-auto border-t border-border-soft px-3 py-2">
            {suggestions.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => void send(item)}
                className="shrink-0 rounded-sm border border-border-soft px-2 py-1 font-sans text-[11px] text-ink-secondary hover:border-mint/40 disabled:opacity-60"
              >
                {item}
              </button>
            ))}
          </div>
          <form onSubmit={onSubmit} className="flex gap-2 border-t border-border-soft p-3">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={listening ? 'Listening...' : 'Ask about your course or progress'}
              maxLength={500}
              className="min-w-0 flex-1 rounded-sm border border-border-soft bg-chalk-warm px-3 py-2 font-sans text-sm"
            />
            <button
              type="button"
              onClick={toggleMic}
              aria-pressed={listening}
              aria-label={listening ? 'Stop microphone and send' : 'Speak your question'}
              className={`inline-flex items-center justify-center rounded-sm px-3 ${
                listening ? 'bg-blush text-white' : 'border border-border-soft text-slate'
              } disabled:opacity-60`}
            >
              <Mic size={16} />
            </button>
            <button
              type="submit"
              disabled={!draft.trim()}
              className="inline-flex items-center justify-center rounded-sm bg-slate px-3 text-chalk disabled:opacity-60"
              aria-label="Send"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="ml-auto flex items-center gap-2 rounded-sm bg-slate px-4 py-3 font-sans text-sm font-semibold text-chalk shadow-md"
      >
        <MessageCircle size={16} />
        Assistant
      </button>
    </div>
  );
}
