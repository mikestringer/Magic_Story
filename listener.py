import os
import threading
import time
import requests
import speech_recognition as sr
import pyaudio


class Listener:
    """
    Listener with two STT backends:
      - STT_PROVIDER=whisper -> POST audio to WHISPER_BASE_URL /transcribe
      - STT_PROVIDER=google  -> recognizer.recognize_google(audio)

    Defaults to google if env var not set.
    """

    def __init__(self, energy_threshold=300, record_timeout=10, device_index=None):
        self.recognizer = sr.Recognizer()

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

        self.stt_provider = os.environ.get("STT_PROVIDER", "google").strip().lower()
        self.whisper_base_url = os.environ.get("WHISPER_BASE_URL", "").strip().rstrip("/")

    def listen(self, ready_callback=None, transcribing_callback=None):
        with self._lock:
            if self._listening:
                return
            self._listening = True
            self._result = ""
            self._done_event.clear()
            self._stop_event.clear()

        def pick_usb_index():
            names = sr.Microphone.list_microphone_names()
            for i, n in enumerate(names):
                if "USB PnP Sound Device" in n:
                    return i
            for i, n in enumerate(names):
                if "USB" in n or "usb" in n:
                    return i
            return None

        def mic_has_input_channels(idx: int) -> bool:
            try:
                pa = pyaudio.PyAudio()
                info = pa.get_device_info_by_index(idx)
                pa.terminate()
                return int(info.get("maxInputChannels", 0)) >= 1
            except Exception:
                return False

        def record():
            try:
                print("DEBUG listener device_index =", self.device_index)
                names = sr.Microphone.list_microphone_names()
                print("DEBUG mic names:", names)

                #idx = self.device_index
                #if idx is None:
                #    idx = pick_usb_index()
                idx = self.device_index
                if idx is None:
                    idx = 2

                if not mic_has_input_channels(idx):
                    print(f"Preferred mic index {idx} not usable, trying auto-detect...")
                    idx = pick_usb_index()

                if idx is None:
                    print("Listener error: Could not find USB mic")
                    return

                if not mic_has_input_channels(idx):
                    print(f"Listener error: Mic index {idx} has no input channels")
                    return

                mic = sr.Microphone(device_index=idx)

                try:
                    with mic as source:
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

                except AttributeError as e:
                    print("Listener mic exit bug:", e)
                    return

                if self._stop_event.is_set():
                    return

                text = ""

                if transcribing_callback:
                    transcribing_callback()

                if self.stt_provider == "whisper":
                    if not self.whisper_base_url:
                        print("WHISPER_BASE_URL not set")
                    else:
                        try:
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

                else:
                    try:
                        text = self.recognizer.recognize_google(audio)
                    except Exception as e:
                        print("Recognition error:", e)

                with self._lock:
                    self._result = text

            except sr.WaitTimeoutError:
                with self._lock:
                    self._result = ""

            except Exception as e:
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
