type RateProvider = () => number;

/** Build a silent WAV clip used as a looping keep-alive to hold the audio device open. */
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
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples * 2, true);
  return new Blob([buffer], { type: "audio/wav" });
}

let _silentLoopUrl: string | null = null;
function silentLoopUrl(): string {
  if (!_silentLoopUrl) _silentLoopUrl = URL.createObjectURL(silentWav(400));
  return _silentLoopUrl;
}

/**
 * Plays pre-synthesized MP3 frames (received over the voice socket) strictly in
 * order. A persistent silent keep-alive loop holds the audio output device open
 * so the first word is never clipped; playback speed follows the user's setting.
 */
export class AudioFrameQueue {
  private getRate?: RateProvider;
  private onIdle?: () => void;
  private queue: ArrayBuffer[] = [];
  private playing = false;
  private stopped = false;
  private current: HTMLAudioElement | null = null;
  private keepAlive: HTMLAudioElement | null = null;

  constructor(getRate?: RateProvider, onIdle?: () => void) {
    this.getRate = getRate;
    this.onIdle = onIdle;
  }

  /** Prepare for a new utterance (call from a user gesture so audio can play). */
  start() {
    this.stopped = false;
    this.ensureWarm();
  }

  push(frame: ArrayBuffer) {
    if (this.stopped) return;
    this.queue.push(frame);
    void this.pump();
  }

  /** True while audio is playing or frames remain queued. */
  isActive(): boolean {
    return this.playing || this.queue.length > 0;
  }

  stop() {
    this.stopped = true;
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

  private ensureWarm() {
    if (this.keepAlive) return;
    const audio = new Audio(silentLoopUrl());
    audio.loop = true;
    audio.volume = 0.02;
    this.keepAlive = audio;
    audio.play().catch(() => {
      this.keepAlive = null;
    });
  }

  private async pump() {
    if (this.playing || this.stopped) return;
    const frame = this.queue.shift();
    if (!frame) {
      this.onIdle?.();
      return;
    }
    this.playing = true;
    const url = URL.createObjectURL(new Blob([frame], { type: "audio/mpeg" }));
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
