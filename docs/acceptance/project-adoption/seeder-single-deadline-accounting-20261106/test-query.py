"""Exercise the real HTTP framing against in-process, synthetic Unix peers."""
from pathlib import Path
import importlib.util
import json
import socket
import sys
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / 'guarded-job-volume-retry-20261105' / 'query.py'
PROJECT = '/test/project'
PAYLOAD = json.dumps({'Volumes': [
    {'Name': 'selected', 'Labels': {'buildctl.project': PROJECT}, 'UsageData': {'Size': 41}},
    {'Name': 'other', 'Labels': {'buildctl.project': '/other'}, 'UsageData': {'Size': 17}},
]}).encode()


def load(path):
    spec = importlib.util.spec_from_file_location(path.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(body=PAYLOAD, status=200):
    return f'HTTP/1.1 {status} Test\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body


def run_sample(module, reply):
    handlers = []
    calls = []
    original = module.UnixHTTP

    def serve(peer, index):
        with peer:
            command = b''
            try:
                while not command.endswith(b'\r\n\r\n'):
                    chunk = peer.recv(4096)
                    if not chunk:
                        return
                    command += chunk
                calls.append(command.splitlines()[0].decode())
                reply(peer, index)
            except (BrokenPipeError, ConnectionResetError):
                pass

    class LocalHTTP(original):
        def connect(self):
            self.sock, peer = socket.socketpair()
            self.sock.settimeout(self.timeout)
            thread = threading.Thread(target=serve, args=(peer, len(handlers)), daemon=True)
            handlers.append(thread)
            thread.start()

    module.UnixHTTP = LocalHTTP
    started = time.monotonic()
    try:
        data = module.sample(PROJECT)
    except (TimeoutError, RuntimeError, ValueError) as error:
        data = type(error).__name__
    finally:
        elapsed = time.monotonic() - started
        module.UnixHTTP = original
    for thread in handlers:
        thread.join(timeout=2)
    return data, elapsed, calls


class AccountingDeadline(unittest.TestCase):
    def setUp(self):
        self.candidate = load(HERE / 'query.py')

    def test_split_deadline_discards_a_completable_slow_request(self):
        def slow(peer, _index):
            time.sleep(4.2)
            peer.sendall(response())

        old, old_elapsed, old_calls = run_sample(load(LEGACY), slow)
        new, new_elapsed, new_calls = run_sample(self.candidate, slow)
        self.assertEqual(old, 'TimeoutError')
        self.assertEqual(len(old_calls), 2)
        self.assertEqual(new['attempts'], 1)
        self.assertEqual([row['Name'] for row in new['Volumes']], ['selected'])
        self.assertEqual(new['Volumes'][0]['UsageData']['Size'], 41)
        self.assertEqual(new_calls, ['GET /v1.53/system/df?type=volume HTTP/1.1'])
        self.assertLess(new_elapsed, 5.1)
        print(json.dumps({'case': 'slow-valid-header', 'legacySeconds': round(old_elapsed, 3),
                          'candidateSeconds': round(new_elapsed, 3), 'candidateRequests': len(new_calls)}))

    def test_cumulative_deadline_refuses_a_dribbling_body(self):
        def trickle(peer, _index):
            header, body = response(PAYLOAD + b' ' * 360).split(b'\r\n\r\n', 1)
            peer.sendall(header + b'\r\n\r\n')
            for offset in range(0, len(body), 30):
                time.sleep(0.65)
                peer.sendall(body[offset:offset + 30])

        result, elapsed, calls = run_sample(self.candidate, trickle)
        self.assertEqual(result, 'TimeoutError')
        self.assertEqual(len(calls), 1)
        self.assertGreater(elapsed, 4.9)
        self.assertLess(elapsed, 5.5)
        print(json.dumps({'case': 'dribbling-body', 'seconds': round(elapsed, 3), 'outcome': 'refused'}))

    def test_invalid_inventories_fail_closed(self):
        for raw in [response(b'{'), response(b'{}'), response(PAYLOAD, 503)]:
            with self.subTest(raw=raw[:40]):
                result, _, calls = run_sample(self.candidate, lambda peer, _: peer.sendall(raw))
                self.assertIn(result, ['RuntimeError', 'JSONDecodeError'])
                self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
