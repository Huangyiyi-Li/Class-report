import base64
import io
import wave
from types import SimpleNamespace
import pytest
from worker.queue_store import QueueStore
from worker.recorder_worker import RecorderWorker, CommandRejected
from worker.config import WorkerConfig


def test_run_summary_waits_for_registration_and_survives_restart(tmp_path):
    store = QueueStore(tmp_path / 'queue.db')
    assert hasattr(store, 'begin_run'), 'recording runs must be persisted'
    store.begin_run('one', '2026-09-08T02:20:00+00:00')
    for i in range(25):
        path = tmp_path / f'{i}.wav'
        path.write_bytes(b'audio')
        store.enqueue({'local_path': str(path), 'segment_index': i + 1, 'recording_id': 'one'})
    store.finish_run('one', '2026-09-08T03:00:00+00:00')
    for i in range(25):
        item = store.claim_next('2026-09-08T04:00:00+00:00')
        store.mark_uploaded(item.id, 'https://example.test/audio')
    summary = store.recent_runs()[0]
    assert summary['segments'] == 25
    assert summary['completed'] == 0
    assert summary['saved'] == 25
    for i in range(25):
        item = store.claim_next('2026-09-08T04:00:00+00:00')
        store.mark_completed(item.id)
    assert QueueStore(tmp_path / 'queue.db').recent_runs()[0]['completed'] == 25


def test_runs_do_not_mix_and_unfinished_runs_are_interrupted(tmp_path):
    store = QueueStore(tmp_path / 'queue.db')
    assert hasattr(store, 'begin_run'), 'recording runs must be persisted'
    store.begin_run('one', '2026-09-08T02:20:00+00:00')
    store.begin_run('two', '2026-09-08T03:20:00+00:00')
    store.interrupt_open_runs()
    assert all(run['interrupted'] for run in store.recent_runs())
    assert all(run['segments'] == 0 for run in store.recent_runs())


def test_microphone_test_uses_memory_and_closes_stream():
    from worker import recorder_worker
    assert hasattr(recorder_worker, 'MicrophoneTest'), 'isolated microphone test is missing'
    seen = {}
    class Stream:
        def start(self): seen['callback'](b'\x00\x10' * 1600, 1600, None, None)
        def stop(self): seen['stopped'] = True
        def close(self): seen['closed'] = True
    def factory(**kwargs):
        seen.update(kwargs)
        return Stream()
    probe = recorder_worker.MicrophoneTest(stream_factory=factory)
    probe.start('USB microphone')
    assert seen['device'] == 'USB microphone'
    assert probe.snapshot()['level'] > 0
    probe.finish()
    result = probe.result()
    with wave.open(io.BytesIO(base64.b64decode(result['audio'])), 'rb') as audio:
        assert audio.getnframes() == 1600
    assert seen['stopped'] and seen['closed']
    probe.cancel()
    assert 'audio' not in probe.result()


def test_testing_cannot_interrupt_active_recording(tmp_path):
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)), emit_event=lambda *args: None)
    worker.state['recording'] = 'recording'
    with pytest.raises(CommandRejected, match='停止录音'):
        worker.execute_command(SimpleNamespace(command='start_microphone_test', payload={'inputDevice': 'default'}))


def test_notice_acknowledgment_is_persisted_without_changing_recording(tmp_path):
    path = tmp_path / 'config.json'
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)), config_path=path, emit_event=lambda *args: None)
    worker.state['recording'] = 'recording'
    worker.execute_command(SimpleNamespace(command='acknowledge_recording_notice', payload={}))
    assert WorkerConfig.load(path).recording_notice_version == 1
    assert worker.state['recording'] == 'recording'


def test_pause_resume_keeps_run_and_stop_creates_new_run(tmp_path):
    from worker.test_recorder_worker import FakeSession, allow_startup, command
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)),
                            session_factory=lambda **kwargs: FakeSession(),
                            startup_gate=allow_startup, emit_event=lambda *args: None)
    worker.execute_command(command('start'))
    first = worker.snapshot()['recentRecordings'][0]['id']
    worker.execute_command(command('pause'))
    worker.execute_command(command('start'))
    assert worker.snapshot()['recentRecordings'][0]['id'] == first
    worker.execute_command(command('stop'))
    assert worker.snapshot()['recentRecordings'][0]['endedAt']
    worker.execute_command(command('start'))
    assert worker.snapshot()['recentRecordings'][0]['id'] != first
    worker.shutdown()


def test_recovered_audio_retains_recording_id(tmp_path):
    from datetime import datetime, timezone
    from worker.audio_journal import AudioJournal, recover_journals
    store = QueueStore(tmp_path / 'queue.db')
    store.begin_run('one', '2026-09-08T02:20:00+00:00')
    journal = AudioJournal(tmp_path, 'test-device', datetime.now(timezone.utc), 16000, 1, 2, recording_id='one')
    journal.append(b'\0\0' * 1600)
    journal.checkpoint()
    journal.file.close()
    recover_journals(tmp_path, queue_store=store)
    assert store.recent_runs()[0]['saved'] == 1


def test_probe_memory_is_bounded_and_silence_is_not_a_positive_level():
    from worker.microphone_test import MicrophoneTest
    class Stream:
        def start(self): pass
        def stop(self): pass
        def close(self): pass
    probe = MicrophoneTest(lambda **kwargs: Stream())
    probe.start('default')
    probe._callback(b'\0\0' * 16000 * 9, 16000 * 9, None, None)
    probe.finish()
    assert probe.result()['seconds'] == 8
    assert probe.result()['peak'] == 0
    probe.cancel()


def test_probe_blocks_start_without_arming_automatic_retry(tmp_path):
    from worker.test_recorder_worker import command
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)), emit_event=lambda *args: None)
    worker.microphone_test._status = 'recording'
    with pytest.raises(CommandRejected, match='结束麦克风测试'):
        worker.execute_command(command('start'))
    assert not worker._desired_recording
    assert not worker._recording_session_active
    worker.shutdown()


def test_failed_resume_marks_run_interrupted(tmp_path):
    from worker.test_recorder_worker import FakeSession, allow_startup, command
    session = FakeSession()
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)),
                            session_factory=lambda **kwargs: session,
                            startup_gate=allow_startup, emit_event=lambda *args: None)
    worker.execute_command(command('start'))
    worker.execute_command(command('pause'))
    def fail(): raise OSError('unplugged')
    session.start = fail
    with pytest.raises(CommandRejected): worker.execute_command(command('start'))
    worker.execute_command(command('stop'))
    assert worker.snapshot()['recentRecordings'][0]['interrupted']
    worker.shutdown()


def test_binding_cannot_start_production_audio_during_probe(tmp_path):
    from worker.test_recorder_worker import command, classroom_binding
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)), config_path=tmp_path / 'config.json', emit_event=lambda *args: None)
    worker.microphone_test._status = 'recording'
    with pytest.raises(CommandRejected, match='结束麦克风测试'):
        worker.execute_command(command('apply_binding', classroom_binding()))
    assert not (tmp_path / 'config.json').exists()
    worker.shutdown()


def test_worker_probe_never_creates_formal_audio_or_queue_entries(tmp_path):
    from worker.test_recorder_worker import command
    from worker.microphone_test import MicrophoneTest
    worker = RecorderWorker(WorkerConfig(data_root=str(tmp_path)), emit_event=lambda *args: None)
    class Stream:
        def start(self): pass
        def stop(self): pass
        def close(self): pass
    worker.microphone_test = MicrophoneTest(lambda **kwargs: Stream())
    worker.execute_command(command('start_microphone_test', {'inputDevice': 'default'}))
    worker.microphone_test._callback(b'\0\0' * 1600, 1600, None, None)
    worker.microphone_test.finish()
    assert worker.execute_command(command('microphone_test_result'))['audio']
    assert 'audio' not in worker.snapshot()['microphoneTest']
    assert worker.queue_store is None
    assert list(tmp_path.iterdir()) == []
    assert worker.state['recording'] == 'idle'
    worker.shutdown()
