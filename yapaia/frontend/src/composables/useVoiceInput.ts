import { ref } from "vue";

export function useVoiceInput() {
  const isListening = ref(false);
  const isSupported =
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

  function start(): Promise<string> {
    return new Promise((resolve, reject) => {
      const SR =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;
      if (!SR) {
        reject(new Error("SpeechRecognition not supported"));
        return;
      }

      const recognition: any = new SR();
      recognition.lang = "de-DE";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.continuous = false;

      recognition.onstart = () => {
        isListening.value = true;
      };
      recognition.onend = () => {
        isListening.value = false;
      };
      recognition.onresult = (e: any) => {
        const transcript = e.results[0][0].transcript;
        resolve(transcript);
      };
      recognition.onerror = (e: any) => {
        isListening.value = false;
        if (e.error === "no-speech") {
          reject(new Error("Keine Spracheingabe erkannt."));
        } else if (e.error === "not-allowed") {
          reject(new Error("Mikrofon-Zugriff verweigert."));
        } else {
          reject(new Error(`Spracherkennung: ${e.error}`));
        }
      };

      recognition.start();
    });
  }

  return { start, isListening, isSupported };
}
