"""Bounded, memory-only probe using the recorder's PortAudio input format."""
import base64
import io
import math
import struct
import threading
import wave


class MicrophoneTest:
    RATE = 16000
    SECONDS = 8

    def __init__(self, stream_factory):
        self.factory = stream_factory
        self._lock = threading.Lock()
        self._lifecycle = threading.RLock()
        self._stream = None
        self._timer = None
        self._expiry = None
        self._pcm = bytearray()
        self._status = 'idle'
        self._level = 0
        self._peak = 0
        self._error = ''

    @property
    def active(self):
        return self._status == 'recording'

    def start(self, device):
        if not isinstance(device, str) or not device.strip() or len(device) > 256:
            raise ValueError('请选择有效的麦克风')
        with self._lifecycle:
            self.cancel()
            with self._lock:
                self._status = 'recording'
            try:
                self._stream = self.factory(callback=self._callback, samplerate=self.RATE,
                                            channels=1, dtype='int16',
                                            device=None if device == 'default' else device)
                self._stream.start()
                self._timer = threading.Timer(self.SECONDS, self.finish)
                self._timer.daemon = True
                self._timer.start()
                self._expiry = threading.Timer(60, self.cancel)
                self._expiry.daemon = True
                self._expiry.start()
            except Exception:
                self.cancel()
                raise ValueError('无法打开所选麦克风，请检查连接和 Windows 麦克风权限')
        return self.snapshot()

    def _callback(self, data, frames, callback_time, status):
        pcm = data if isinstance(data, bytes) else data.copy().tobytes()
        with self._lock:
            if self._status != 'recording':
                return
            if status:
                self._error = '试录采集不连续，请重新测试'
            remaining = self.RATE * self.SECONDS * 2 - len(self._pcm)
            pcm = pcm[:remaining - remaining % 2]
            self._pcm.extend(pcm)
            if pcm:
                samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
                rms = math.sqrt(sum(x * x for x in samples) / len(samples)) / 32768
                self._level = min(100, round(rms * 300))
                self._peak = max(self._peak, self._level)

    def _close(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None
        stream, self._stream = self._stream, None
        if stream:
            try:
                stream.stop()
            finally:
                stream.close()

    def finish(self):
        with self._lifecycle:
            if not self.active:
                return
            try:
                self._close()
            except Exception:
                self._error = '麦克风释放异常，请重新测试'
            with self._lock:
                self._status = 'ready' if self._pcm else 'error'
                if not self._pcm:
                    self._error = '没有收到音频，请检查麦克风连接和权限'

    def cancel(self):
        with self._lifecycle:
            if self._expiry:
                self._expiry.cancel()
                self._expiry = None
            with self._lock:
                self._status = 'idle'
            try:
                self._close()
            finally:
                with self._lock:
                    self._pcm.clear()
                    self._level = self._peak = 0
                    self._error = ''

    def snapshot(self):
        with self._lock:
            return {'status': self._status, 'level': self._level, 'peak': self._peak,
                    'seconds': round(len(self._pcm) / (self.RATE * 2), 1), 'error': self._error}

    def result(self):
        result = self.snapshot()
        with self._lock:
            if self._status == 'ready':
                output = io.BytesIO()
                with wave.open(output, 'wb') as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(self.RATE)
                    audio.writeframes(bytes(self._pcm))
                result['audio'] = base64.b64encode(output.getvalue()).decode('ascii')
        return result
