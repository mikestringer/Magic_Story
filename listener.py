import os
import time
import json
import queue
import threading

import pyaudio
from vosk import Model, KaldiRecognizer


class Listener:
    """
    Local/offline speech-to-text listener using Vosk.

    Expected API (from your book script):
      - listen(ready_callback=None)
      - speech_waiting() -> bool
      - recognize() -> str
      - is_listening() -> bool
      - stop_listening()
    """

    def __init__(
        self,
        energy_threshold: int = 300,     # kept for compatibility; Vosk doesn't use this directly
        record_timeout: int = 30,
        model_path: str | None = None,
        sample_rate: int = 16000,
        device_index: int | None = None,
        min_utterance_seconds: float = 0.8,
        end_silence_seconds: float = 1.0,
    ):
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.sample_rate = sample_rate
        self.device_index = device_index
        self.min_utterance_seconds = min_utterance_seconds
        self.end_silence_seconds = end_silence_seconds

        # Where the Vosk model lives (env var overrides)
        self.model_path = (
            os.environ.get("VOSK_MODEL_PATH")
            or model_path
            or os.path.join(os.path.dirname(__file__), "vosk-model-small-en-us-0.15")
        )
        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(
                f"Vosk model not found at '{self.model_path}'. "
                f"Set VOSK_MODEL_PATH or place the model folder next to listener.py."
            )

        self._model = Model(self.model_path)
        self._recognizer = KaldiRecognizer(self._model, self.sample_rate)
        # A little more permissive for natural classroom prompts:
        self._recognizer.SetWords(True)

        self._audio = pyaudio.PyAudio()
        self._stream = None

        self._thread = None
        self._stop_event = threading.Event()

        self._results_q = queue.Queue()
        self._listening = False

    def listen(self, ready_callback=None):
        """Start listening in a background thread."""
        if self._listening:
            return

        self._stop_event.clear()
        self._results_q = queue.Queue()

        def run():
            self._listening = True
            try:
                self._open_stream()
                if ready_callback:
                    ready_callback()

                start_time = time.monotonic()
                last_speech_time = None
                utterance_started = None
                partial_seen = False

                # Read audio until we detect end-of-utterance OR timeout
                while not self._stop_event.is_set():
                    if (time.monotonic() - start_time) > self.record_timeout:
                        break

                    data = self._stream.read(4000, exception_on_overflow=False)

                    # AcceptWaveform returns True when it thinks an utterance segment is complete
                    if self._recognizer.AcceptWaveform(data):
                        res = json.loads(self._recognizer.Result() or "{}")
                        text = (res.get("text") or "").strip()
                        if text:
                            self._results_q.put(text)
                            break
                    else:
                        pres = json.loads(self._recognizer.PartialResult() or "{}")
                        partial = (pres.get("partial") or "").strip()
                        if partial:
                            partial_seen = True
                            now = time.monotonic()
                            last_speech_time = now
                            if utterance_started is None:
                                utterance_started = now
                        else:
                            # No partial currently; if we had speech before, check silence timeout
                            if partial_seen and last_speech_time is not None:
                                if (time.monotonic() - last_speech_time) >= self.end_silence_seconds:
                                    # finalize whatever is in the decoder
                                    fres = json.loads(self._recognizer.FinalResult() or "{}")
                                    ftext = (fres.get("text") or "").strip()
                                    if ftext:
                                        # ensure it’s not a tiny blip
                                        if utterance_started and (time.monotonic() - utterance_started) >= self.min_utterance_seconds:
                                            self._results_q.put(ftext)
                                    break

                # Finalize if nothing queued
                if self._results_q.empty() and not self._stop_event.is_set():
                    fres = json.loads(self._recognizer.FinalResult() or "{}")
                    ftext = (fres.get("text") or "").strip()
                    if ftext:
                        self._results_q.put(ftext)

            finally:
                self._close_stream()
                self._listening = False

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def speech_waiting(self) -> bool:
        return not self._results_q.empty()

    def recognize(self) -> str:
        """Return the recognized text (blocks briefly if needed)."""
        try:
            # small wait in case result is about to land
            return self._results_q.get(timeout=0.5)
        except queue.Empty:
            return ""

    def is_listening(self) -> bool:
        return self._listening

    def stop_listening(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._close_stream()
        self._listening = False

    def _open_stream(self):
        if self._stream is not None:
            return

        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=4000,
            input_device_index=self.device_index,
        )
        self._stream.start_stream()

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
