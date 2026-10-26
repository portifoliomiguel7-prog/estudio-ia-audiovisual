import array
import copy
import hashlib
import http.server
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request
import wave

import config
import obs_control
import prepare_reference
import project
import studio


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        local = config.CODE / '.local'
        local.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=local)
        self.root = Path(self.temp.name).resolve()
        self.patches = [patch.object(studio, 'ROOT', self.root),
                        patch.object(studio, 'PROD', self.root),
                        patch.object(studio, 'PLAN', self.root / 'plan.json'),
                        patch.object(studio, 'CLONE', self.root / 'voice-clone')]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        assert self.root.is_relative_to((config.CODE / '.local').resolve())
        self.temp.cleanup()


class PathTests(WorkspaceCase):
    def test_escape_and_windows_absolute_paths_rejected(self):
        for value in ['../private/voice.wav', '/outside', 'C:/outside', r'..\outside']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                config.safe_child(self.root, value)

    def test_regular_child_allowed(self):
        self.assertEqual(config.safe_child(self.root, 'output/a.wav'), self.root / 'output/a.wav')

    def test_symlink_to_private_file_rejected(self):
        secret = self.root / 'private.txt'
        secret.write_text('test-only', encoding='utf-8')
        link = self.root / 'alias'
        try:
            link.symlink_to(secret)
        except OSError:
            self.skipTest('System does not permit symlink creation; containment tests still run')
        with self.assertRaises(ValueError):
            config.safe_child(self.root, 'alias')

    def test_voice_requires_operator_consent(self):
        with self.assertRaisesRegex(ValueError, 'consent'):
            prepare_reference.prepare('missing.wav', 0, 12, False)


class HttpTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        studio.STATE.update(running=False, outputs=[], message='test-only')
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), studio.Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.origin = patch.object(studio, 'ORIGIN', self.url)
        self.token = patch.object(studio, 'TOKEN', 'test-only')
        self.origin.start()
        self.token.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.origin.stop()
        self.token.stop()
        super().tearDown()

    def request(self, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers=headers or {})
        return urllib.request.urlopen(req, timeout=3)

    def test_home_and_empty_plan(self):
        with self.request('/') as result:
            self.assertIn('Estúdio IA Audiovisual', result.read().decode())
        with self.request('/api/plan') as result:
            self.assertEqual(json.load(result)['scenes'], [])

    def test_nonce_required(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/api/save', {'scenes': []})
        self.assertEqual(caught.exception.code, 403)

    def test_wrong_origin_and_host_rejected(self):
        for headers in [{'X-Studio-Token': 'test-only', 'Origin': 'https://example.invalid'},
                        {'X-Studio-Token': 'test-only', 'Host': 'example.invalid'}]:
            with self.subTest(headers=headers), self.assertRaises(urllib.error.HTTPError) as caught:
                self.request('/api/save', {}, headers)
            self.assertEqual(caught.exception.code, 403)

    def test_private_model_code_and_raw_are_not_served(self):
        for path in ['/voice-clone/private/reference-12s.wav', '/.git/config',
                     '/studio.py', '/raw/a.mkv', '/server.json', '/output/%2e%2e/private.txt']:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as caught:
                self.request(path)
            self.assertEqual(caught.exception.code, 403)

    def test_valid_save_and_busy_rejection(self):
        plan = {'voice': 'Microsoft Maria Desktop', 'rate': 0, 'scenes': []}
        headers = {'X-Studio-Token': 'test-only', 'Origin': self.url}
        with self.request('/api/save', plan, headers) as result:
            self.assertTrue(json.load(result)['ok'])
        self.assertEqual(json.loads((self.root / 'plan.json').read_text()), plan)
        studio.STATE['running'] = True
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request('/api/render', {}, headers)
        self.assertEqual(caught.exception.code, 409)
        studio.STATE['running'] = False


class ObsTests(unittest.TestCase):
    def test_existing_recording_is_never_stopped(self):
        client = Mock()
        client.send.return_value = {'outputActive': True}
        with self.assertRaisesRegex(ValueError, 'existente'):
            obs_control.record(client, 3, True, True)
        self.assertEqual(client.send.call_count, 1)
        self.assertEqual(client.send.call_args.args[0], 'GetRecordStatus')

    def test_record_requires_preview_and_audio_review(self):
        client = Mock()
        with self.assertRaises(ValueError):
            obs_control.record(client, 3)
        client.send.assert_not_called()

    def test_record_stop_and_validation_for_own_recording(self):
        (config.CODE / '.local').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=config.CODE / '.local') as directory:
            root = Path(directory)
            source = root / 'source.mkv'
            source.write_bytes(b'test-only')
            calls = []
            def send(kind, **kwargs):
                calls.append(kind)
                if kind == 'GetRecordStatus':
                    return {'outputActive': len(calls) > 1}
                if kind == 'StopRecord':
                    return {'outputPath': str(source)}
                return {}
            client = Mock()
            client.send.side_effect = send
            with patch.object(obs_control, 'workspace', return_value=root), \
                 patch.object(obs_control.time, 'sleep'), patch.object(obs_control.subprocess, 'run'):
                result = obs_control.record(client, 3, True, True)
            self.assertEqual(calls, ['GetRecordStatus', 'StartRecord', 'GetRecordStatus', 'StopRecord'])
            self.assertTrue(source.exists() and Path(result['file']).exists())


class RenderTests(WorkspaceCase):
    def setUp(self):
        super().setUp()
        raw = self.root / 'raw'
        raw.mkdir()
        imports = self.root / 'imports'
        imports.mkdir()
        self.source = raw / 'test.mkv'
        subprocess.run([studio.FF, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                        '-i', 'color=c=blue:s=160x90:r=10', '-t', '5', '-c:v', 'libx264',
                        str(self.source)], check=True)
        samples = array.array('h', [int(8000 * math.sin(i * 2 * math.pi * 440 / 24000)) for i in range(12000)])
        with wave.open(str(imports / 'tone.wav'), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(samples.tobytes())
        self.plan = {'voice': 'Microsoft Maria Desktop', 'rate': 0, 'scenes': [
            {'scene': n, 'file': 'test.mkv', 'title': 'Synthetic test fixture', 'duration': 5,
             'cues': [{'start': .2, 'text': 'Test fixture only', 'audio': 'tone.wav'}]}
            for n in [1, 2]]}
        studio.save(self.plan, self.root / 'plan.json')

    def test_two_scene_render_decode_and_source_preservation(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        output = studio.render()
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['scenes']), 2)
        self.assertEqual(manifest['full_video'], 'video-completo.mp4')
        self.assertTrue((output / 'video-completo.mp4').is_file())
        self.assertTrue(all(scene['decode'] == 'PASS' and scene['audio_peak_pcm16'] > 0 for scene in manifest['scenes']))
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)

    def test_overrun_is_rejected_instead_of_cutting_audio(self):
        self.plan['scenes'][0]['cues'].append({'start': .4, 'text': 'Test', 'audio': 'tone.wav'})
        studio.save(self.plan, self.root / 'plan.json')
        with self.assertRaisesRegex(ValueError, 'Nenhum áudio foi cortado'):
            studio.render(1)

    def test_scene_ids_are_not_limited_to_seven(self):
        self.plan['scenes'][0]['scene'] = 12
        studio.validate(self.plan)

    def test_import_measures_duration_without_changing_original(self):
        with patch.object(project, 'workspace', return_value=self.root / 'new-project'):
            before = self.source.read_bytes()
            result = project.add_video(self.source)
        self.assertEqual(result['scene'], 1)
        self.assertAlmostEqual(result['duration'], 5, places=1)
        self.assertEqual(self.source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
