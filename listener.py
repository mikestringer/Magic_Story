import speech_recognition as sr
import threading

class Listener:

    def __init__(self, energy_threshold=300, record_timeout=10):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold

        # 🔧 Silence tuning
        self.recognizer.pause_threshold = 1.5          # wait longer before assuming done
        self.recognizer.non_speaking_duration = 1.0    # allow short pauses
        self.recognizer.dynamic_energy_threshold = True

        self.record_timeout = record_timeout
        self._result = ""
        self._listening = False

    def listen(self, ready_callback=None):
        self._listening = True
        self._result = ""

        def record():
            with sr.Microphone() as source:
                if ready_callback:
                    ready_callback()
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=self.record_timeout, phrase_time_limit=None)

            try:
                text = self.recognizer.recognize_google(audio)
                self._result = text
            except Exception as e:
                print("Recognition error:", e)
                self._result = ""

            self._listening = False

        threading.Thread(target=record, daemon=True).start()

    def speech_waiting(self):
        return not self._listening and bool(self._result)

    def recognize(self):
        return self._result

    def is_listening(self):
        return self._listening

    def stop_listening(self):
        self._listening = False
