type Synthesize = (text: string) => Promise<Blob>;
type RateProvider = () => number;

/** Build a silent WAV clip (used as a looping keep-alive to hold the audio device open). */
function silentWav(ms: number, sampleRate = 24000): Blob {
  const samples = Math.floor((sampleRate * ms) / 1000);
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const writeStr = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true); // PCM header size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, "data");
  view.setUint32(40, samples * 2, true);
  // Sample data is left as zeros (pure silence).
  return new Blob([buffer], { type: "audio/wav" });
}

let _silentLoopUrl: string | null = null;
function silentLoopUrl(): string {
  if (!_silentLoopUrl) _silentLoopUrl = URL.createObjectURL(silentWav(400));
  return _silentLoopUrl;
}

/**
 * Speaks streamed assistant text with minimal latency.
 *
 * As tokens arrive we split off complete sentences and immediately kick off
 * their synthesis (in parallel). Audio is played strictly in order, so the
 * first sentence starts playing while the rest of the reply is still streaming.
 *
 * A persistent, silent keep-alive loop holds the audio output device open while
 * voice is active, so the device never sleeps and the first word is not clipped.
 */
export class SpeechQueue {
  private synth: Synthesize;
  private getRate?: RateProvider;
  private buffer = "";
  private queue: Promise<Blob | null>[] = [];
  private playing = false;
  private stopped = true;
  private current: HTMLAudioElement | null = null;
  private keepAlive: HTMLAudioElement | null = null;

  constructor(synth: Synthesize, getRate?: RateProvider) {
    this.synth = synth;
    this.getRate = getRate;
  }

  /** Begin a fresh utterance, cancelling anything currently playing/queued. */
  start() {
    this.stop();
    this.stopped = false;
    this.ensureWarm();
  }

  /** Feed a streamed chunk of text. */
  push(delta: string) {
    if (this.stopped) return;
    this.buffer += delta;
    let idx: number;
    while ((idx = this.boundary(this.buffer)) !== -1) {
      const sentence = this.buffer.slice(0, idx + 1).trim();
      this.buffer = this.buffer.slice(idx + 1);
      if (sentence) this.enqueue(sentence);
    }
  }

  /** Flush the trailing partial sentence once the stream is done. */
  flush() {
    if (this.stopped) return;
    const rest = this.buffer.trim();
    this.buffer = "";
    if (rest) this.enqueue(rest);
  }

  /** Convenience for one-shot playback of a full text (e.g. manual replay). */
  speak(text: string) {
    this.start();
    this.push(text);
    this.flush();
  }

  /** Stop playback, clear the queue, and release the keep-alive loop. */
  stop() {
    this.stopped = true;
    this.buffer = "";
    this.queue = [];
    this.playing = false;
    if (this.current) {
      this.current.onended = null;
      this.current.onerror = null;
      this.current.pause();
      this.current = null;
    }
    if (this.keepAlive) {
      this.keepAlive.pause();
      this.keepAlive = null;
    }
  }

  // Start (or keep) a looping silent track so the OS keeps the audio output
  // device active; otherwise it sleeps and clips the start of the next clip.
  private ensureWarm() {
    if (this.keepAlive) return;
    const audio = new Audio(silentLoopUrl());
    audio.loop = true;
    audio.volume = 0.02; // inaudible (samples are silent) but counts as active playback
    this.keepAlive = audio;
    audio.play().catch(() => {
      this.keepAlive = null;
    });
  }

  // A period only counts as a boundary when followed by whitespace (so prices
  // like "6.50" don't split); ! ? newline and the Greek ; / · always do.
  private boundary(text: string): number {
    const m = /\.(?=\s)|[!?\n;·]/.exec(text);
    return m ? m.index : -1;
  }

  private enqueue(sentence: string) {
    const job = this.synth(sentence).catch(() => null);
    this.queue.push(job);
    void this.pump();
  }

  private async pump() {
    if (this.playing || this.stopped) return;
    const next = this.queue.shift();
    if (!next) return;

    this.playing = true;
    const blob = await next;
    if (this.stopped || !blob) {
      this.playing = false;
      void this.pump();
      return;
    }

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = this.getRate?.() ?? 1;
    this.current = audio;
    const advance = () => {
      URL.revokeObjectURL(url);
      if (this.current === audio) this.current = null;
      this.playing = false;
      void this.pump();
    };
    audio.onended = advance;
    audio.onerror = advance;
    try {
      await audio.play();
    } catch {
      advance();
    }
  }
}
