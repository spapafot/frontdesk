import { API_BASE } from "./client";

export async function transcribeAudio(blob: Blob, language?: string): Promise<string> {
  const form = new FormData();
  const ext = blob.type.includes("mp4") ? "mp4" : "webm";
  form.append("file", blob, `audio.${ext}`);
  if (language) form.append("language", language);

  const response = await fetch(`${API_BASE}/speech/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Transcription failed (${response.status}): ${detail}`);
  }
  const data = (await response.json()) as { text: string };
  return data.text;
}

export async function synthesizeSpeech(text: string, voice?: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}/speech/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(voice ? { text, voice } : { text }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Speech synthesis failed (${response.status}): ${detail}`);
  }
  return await response.blob();
}
