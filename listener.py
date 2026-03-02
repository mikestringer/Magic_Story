import os
import threading
import time
import requests
import speech_recognition as sr


class Listener:
    """
    Listener with two STT backends:
      - STT_PROVIDER=whisper -> POST audio to WHISPER_BASE_URL /transcribe
      - STT_PROVIDER=google  -> recognizer.recognize_google(audio)

    Defaults to google if env var not set.
    """

    def __init__(self, energy_threshold=300, record_timeout=10, device_index=None):
        self.recognizer = sr.Recognizer()

        # Keep your key tuning items
        self.recognizer.pause_threshold = 2.5
        self.recognizer.non_speaking_duration = 1.0
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = energy_threshold

        self.record_timeout = record_timeout
        self.device_index = device_index

        self._result = ""
        self._listening = False

        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = None

        # STT config via env
        self.stt_provider = os.environ.get("STT_PROVIDER", "google").strip().lower()
        self.whisper_base_url = os.environ.get("WHISPER_BASE_URL", "").strip().rstrip("/")

    def listen(self, ready_callback=None):
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._result = ""
            self._done_event.clear()
            self._stop_event.clear()

        def record():
            try:
                print("DEBUG listener device_index =", self.device_index)
                print("DEBUG mic names:", sr.Microphone.list_microphone_names())
                mic = sr.Microphone(device_index=self.device_index)
                with mic as source:
                    # Light ambient calibration helps in classrooms
                    try:
                        self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    except Exception:
                        pass

                    if ready_callback:
                        ready_callback()

                    if self._stop_event.is_set():
                        return

                    print("Listening...")
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.record_timeout,
                        phrase_time_limit=None,
                    )

                if self._stop_event.is_set():
                    return

                text = ""
                if self.stt_provider == "whisper":
                    if not self.whisper_base_url:
                        print("Listener error: STT_PROVIDER=whisper but WHISPER_BASE_URL is not set")
                        text = ""
                    else:
                        try:
                            # Convert to mono 16kHz 16-bit WAV for consistency
                            wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
                            files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
                            r = requests.post(
                                f"{self.whisper_base_url}/transcribe",
                                files=files,
                                timeout=5,
                            )
                            r.raise_for_status()
                            data = r.json()
                            text = (data.get("text") or "").strip()
                        except Exception as e:
                            print("Whisper STT error:", e)
                            text = ""
                else:
                    try:
                        text = self.recognizer.recognize_google(audio)
                    except Exception as e:
                        print("Recognition error:", e)
                        text = ""

                with self._lock:
                    self._result = text

            except sr.WaitTimeoutError:
                with self._lock:
                    self._result = ""

            except Exception as e:
                # ALSA/PortAudio errors shouldn't crash the whole program
                print("Listener error:", e)
                with self._lock:
                    self._result = ""

            finally:
                with self._lock:
                    self._listening = False
                self._done_event.set()

        self._thread = threading.Thread(target=record, daemon=True)
        self._thread.start()

    def speech_waiting(self):
        # finished (result may be empty)
        return self._done_event.is_set()

    def recognize(self):
        return self._result

    def is_listening(self):
        with self._lock:
            return self._listening

    def stop_listening(self):
        self._stop_event.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=0.5)
        with self._lock:
            self._listening = False
        self._done_event.set()
