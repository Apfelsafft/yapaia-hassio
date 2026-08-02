import { usePreferencesStore } from "../stores/preferences";

export function speak(text: string): void {
  if (typeof speechSynthesis === "undefined") return;
  const prefs = usePreferencesStore();
  if (prefs.data.tts_enabled === false) return;

  speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = "de-DE";
  utt.rate = 1.05;
  utt.volume = 1.0;
  speechSynthesis.speak(utt);
}
