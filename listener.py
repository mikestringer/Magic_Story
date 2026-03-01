import speech_recognition as sr
import threading
import time


class Listener:
    """
    Google SpeechRecognition listener (recognize_google) with:
      - your silence tuning preserved
      - thread-safe single active recording
      - safe handling of ALSA/PortAudio errors
      - speech_waiting() returns True when the attempt is finished
        (even if result is empty), preventing rapid re-entry crashes
    """

    def __init__(self, energy_threshold=300, record_timeout=10, device_index=None):
        self.recognizer = sr.Recognizer()

        # ✅ Keep your key tuning items
        self.recognizer.pause_threshold = 2.5          # wait longer before assuming done
        self.recognizer.non_speaking_duration = 1.0    # allow short pauses
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = energy_threshold

        self.record_timeout = record_timeout
        self.device_index = device_index

        self._result = ""
        self._listening = False

        # ✅ New: concurrency + lifecycle safety
        self._lock = threading.Lock()
        self._done_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread = None

    def listen(self, ready_callback=None):
        """
        Start listening in a background thread.
        If already listening, do nothing.
        """
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._result = ""
            self._done_event.clear()
            self._stop_event.clear()

        def record():
            try:
                mic = sr.Microphone(device_index=self.device_index)
                with mic as source:
                    # Optional: quick ambient calibration helps in noisy rooms
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
                        phrase_time_limit=None,  # stop based on pause_threshold
                    )

                if self._stop_event.is_set():
                    return

                try:
                    text = self.recognizer.recognize_google(audio)
                except Exception as e:
                    print("Recognition error:", e)
                    text = ""

                with self._lock:
                    self._result = text

            except sr.WaitTimeoutError:
                # No speech detected within timeout
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
        """
        True when the listening attempt has finished (result may be empty).
        This prevents the UI from triggering multiple overlapping recordings.
        """
        return self._done_event.is_set()

    def recognize(self):
        return self._result

    def is_listening(self):
        with self._lock:
            return self._listening

    def stop_listening(self):
        """
        We can't reliably interrupt PyAudio mid-read, but we can signal
        to ignore results and let the thread unwind.
        """
        self._stop_event.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=0.5)
        with self._lock:
            self._listening = False
        self._done_event.set()
