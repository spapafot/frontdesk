import { API_BASE } from "./client";

export interface Settings {
  business_name: string;
  assistant_name: string;
  custom_instructions: string | null;
  tts_voice: string;
  tts_speed: number;
}

export interface VoiceOption {
  id: string;
  label: string;
}

// Curated OpenAI TTS voices with perceived-gender hints for the picker.
export const VOICE_OPTIONS: VoiceOption[] = [
  { id: "nova", label: "Nova (female)" },
  { id: "shimmer", label: "Shimmer (female)" },
  { id: "coral", label: "Coral (female)" },
  { id: "sage", label: "Sage (female)" },
  { id: "alloy", label: "Alloy (neutral)" },
  { id: "echo", label: "Echo (male)" },
  { id: "onyx", label: "Onyx (male)" },
  { id: "ash", label: "Ash (male)" },
];

export const SPEED_OPTIONS: { value: number; label: string }[] = [
  { value: 0.9, label: "0.9x (slower)" },
  { value: 1.0, label: "1x (normal)" },
  { value: 1.1, label: "1.1x" },
  { value: 1.25, label: "1.25x" },
  { value: 1.5, label: "1.5x (faster)" },
];

export const settingsKey = `${API_BASE}/settings`;

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getSettings(): Promise<Settings> {
  return handle(await fetch(settingsKey));
}

export async function updateSettings(payload: {
  business_name: string;
  assistant_name: string;
  custom_instructions: string;
  tts_voice: string;
  tts_speed: number;
}): Promise<Settings> {
  return handle(
    await fetch(settingsKey, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
}
