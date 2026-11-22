#!/usr/bin/env python3
"""Real Linux DAC/socket integration tests; never target Android or /dev/socket.

The harness needs root only to construct uid/gid fixtures and drop child UIDs.
The watcher always runs as 1001:1001 with no effective/permitted capabilities.
Unsupported host/identity returns 77, not a claimed pass. No sysctl is changed.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

RADIO = 1001
GPS = 1021
OPTIONS = None
RESULTS = None

SERVER = r'''
import os,socket,sys
path=sys.argv[1];mode=int(sys.argv[2],8)
os.umask(0o077)  # Reproduce the producer mask in this isolated test process.
server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
server.bind(path)
os.chmod(path,mode)
server.listen(8)
print('READY',flush=True)
while True:
    connection,_=server.accept()
    with connection:
        connection.settimeout(3)
        request=connection.recv(128)
        if request==b'create-file':
            fd=os.open(path+'.umask-probe',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o666)
            os.close(fd)
            connection.sendall(b'CREATED')
        else:
            connection.sendall(b'OK')
'''

CLIENT = r'''
import errno,socket,sys
client=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
client.settimeout(3)
try:
    client.connect(sys.argv[1])
    client.sendall(sys.argv[2].encode())
    print(client.recv(128).decode())
except OSError as error:
    print('ERRNO='+str(error.errno))
    raise SystemExit(3 if error.errno==errno.EACCES else 4)
'''


def credentials(uid, gid, groups):
    def apply():
        os.setgroups(groups)
        os.setgid(gid)
        os.setuid(uid)
    return apply


def wait_until(predicate, timeout=8, message='condition did not become true'):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if predicate():
                return
        except FileNotFoundError:
            pass
        time.sleep(0.025)
    raise AssertionError(message)


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class WatcherIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = RESULTS
        cls.binary = cls.results / 'watcher-linux-test'
        command = [OPTIONS.cxx, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                   '-DKLEE_SOCKET_WATCHER_TESTING', str(OPTIONS.source.resolve()),
                   '-o', str(cls.binary)]
        (cls.results / 'compiler-command.json').write_text(json.dumps(command, indent=2) + '\n')
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, check=False)
        (cls.results / 'compiler.log').write_text(completed.stdout)
        if completed.returncode:
            raise RuntimeError('Native Linux compile failed:\n' + completed.stdout)
        # The harness can inherit umask077. Only this fixture executable is
        # made searchable/executable by the deliberately unprivileged child.
        os.chmod(cls.binary, 0o755)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='case-', dir=str(self.results))
        self.base = Path(self.temporary.name)
        os.chmod(self.base, 0o755)
        self.directory = self.base / 'qcrild'
        self.processes = []
        self.watcher = None
        self.log_path = self.results / (self._testMethodName + '.watcher.log')
        self.log_stream = self.log_path.open('wb')
        self.make_directory()

    def tearDown(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(process.pid, signal.SIGCONT)
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=4)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        self.log_stream.close()
        self.temporary.cleanup()  # Only this harness-created case directory.

    def make_directory(self):
        self.directory.mkdir()
        os.chown(self.directory, RADIO, RADIO)
        os.chmod(self.directory, 0o750)

    def start_watcher(self, expect_directory=True):
        self.watcher = subprocess.Popen(
            [str(self.binary), '--directory', str(self.directory)],
            stdin=subprocess.DEVNULL, stdout=self.log_stream, stderr=self.log_stream,
            preexec_fn=credentials(RADIO, RADIO, [RADIO]))
        self.processes.append(self.watcher)
        if expect_directory:
            wait_until(lambda: 'watch-attached' in self.log(), message='watch did not attach')
        else:
            wait_until(lambda: 'directory-unavailable' in self.log(), message='absence was not observed')
        self.assertIsNone(self.watcher.poll(), self.log())
        status = Path('/proc/%d/status' % self.watcher.pid).read_text()
        fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
        self.assertEqual(set(map(int, fields['Uid'].split())), {RADIO})
        self.assertEqual(set(map(int, fields['Gid'].split())), {RADIO})
        for key in ('CapEff', 'CapPrm', 'CapInh', 'CapAmb'):
            if key in fields:
                self.assertEqual(int(fields[key].strip(), 16), 0, key)
        self.assertEqual(fields.get('NoNewPrivs', '').strip(), '1')
        return self.watcher

    def log(self):
        return self.log_path.read_text(errors='replace')

    def start_server(self, name='rild0', uid=RADIO, gid=RADIO, permissions=0o700):
        path = self.directory / name
        process = subprocess.Popen(
            [sys.executable, '-I', '-B', '-c', SERVER, str(path), format(permissions, 'o')],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, preexec_fn=credentials(uid, gid, [gid]))
        self.processes.append(process)
        readable, _, _ = select.select([process.stdout], [], [], 5)
        if not readable or process.stdout.readline().strip() != 'READY':
            if process.poll() is None:
                process.kill()
            process.wait(timeout=4)
            self.fail('Test server failed: ' + process.stderr.read())
        return process, path

    def client(self, path, uid=GPS, gid=1000, groups=(RADIO,), request='ping'):
        return subprocess.run(
            [sys.executable, '-I', '-B', '-c', CLIENT, str(path), request],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=5, check=False,
            preexec_fn=credentials(uid, gid, list(groups)))

    def wait_repaired(self, path):
        wait_until(lambda: mode(path) == 0o720, message='socket was not repaired:\n' + self.log())
        self.assertIsNone(self.watcher.poll(), self.log())

    def test_real_dac_baseline_then_repair_and_no_capabilities(self):
        _, path = self.start_server()
        before = os.lstat(path)
        self.assertEqual(mode(path), 0o700)
        self.assertEqual(self.client(path, uid=RADIO, gid=RADIO).stdout.strip(), 'OK')
        baseline = self.client(path)
        self.assertEqual(baseline.returncode, 3, baseline.stdout + baseline.stderr)
        self.assertIn('ERRNO=13', baseline.stdout)
        self.start_watcher()
        self.wait_repaired(path)
        after = os.lstat(path)
        self.assertEqual((before.st_dev, before.st_ino, before.st_uid, before.st_gid),
                         (after.st_dev, after.st_ino, after.st_uid, after.st_gid))
        self.assertEqual(self.client(path).stdout.strip(), 'OK')
        without_radio = self.client(path, groups=())
        self.assertEqual(without_radio.returncode, 3, without_radio.stdout)

    def test_same_name_new_socket_inode_is_repaired_again(self):
        server, path = self.start_server()
        self.start_watcher()
        self.wait_repaired(path)
        old = os.lstat(path)
        pinned = os.open(path, os.O_PATH | os.O_NOFOLLOW)
        try:
            server.terminate()
            server.wait(timeout=4)
            path.unlink()
            _, replacement = self.start_server()
            self.wait_repaired(replacement)
            self.assertNotEqual(old.st_ino, os.lstat(replacement).st_ino)
            self.assertEqual(self.client(replacement).stdout.strip(), 'OK')
        finally:
            os.close(pinned)

    def test_start_before_directory_exists(self):
        self.directory.rmdir()
        self.start_watcher(expect_directory=False)
        self.make_directory()
        _, path = self.start_server('rild1')
        self.wait_repaired(path)
        self.assertEqual(self.client(path).stdout.strip(), 'OK')

    def test_directory_replacement_reattaches_and_leaves_old_directory(self):
        _, old_path = self.start_server()
        self.start_watcher()
        self.wait_repaired(old_path)
        old_directory = self.base / 'retired-qcrild'
        self.directory.rename(old_directory)
        self.make_directory()
        _, path = self.start_server('rild1')
        self.wait_repaired(path)
        wait_until(lambda: self.log().count('watch-attached') >= 2)
        retired = old_directory / 'rild0'
        os.chmod(retired, 0o700)
        time.sleep(1.4)
        self.assertEqual(mode(retired), 0o700)
        self.assertEqual(self.client(path).stdout.strip(), 'OK')

    def test_symlink_and_regular_file_are_rejected(self):
        victim = self.base / 'unrelated-file'
        victim.write_bytes(b'untouched')
        os.chown(victim, RADIO, RADIO)
        os.chmod(victim, 0o700)
        (self.directory / 'rild0').symlink_to(victim)
        ordinary = self.directory / 'rild1'
        ordinary.write_bytes(b'not a socket')
        os.chown(ordinary, RADIO, RADIO)
        os.chmod(ordinary, 0o700)
        self.start_watcher()
        time.sleep(1.4)
        self.assertEqual(mode(victim), 0o700)
        self.assertEqual(victim.read_bytes(), b'untouched')
        self.assertEqual(mode(ordinary), 0o700)
        self.assertTrue((self.directory / 'rild0').is_symlink())
        self.assertGreaterEqual(self.log().count('reason=not-socket'), 2)

    def test_wrong_uid_and_wrong_gid_sockets_are_rejected(self):
        _, first = self.start_server('rild0', uid=0, gid=0)
        _, second = self.start_server('rild1', uid=RADIO, gid=1000)
        self.start_watcher()
        time.sleep(1.4)
        self.assertEqual(mode(first), 0o700)
        self.assertEqual(mode(second), 0o700)
        self.assertGreaterEqual(self.log().count('reason=not-radio-owner-and-group'), 2)

    def test_unexpected_modes_and_non_whitelist_socket_are_unchanged(self):
        _, first = self.start_server('rild0', permissions=0o600)
        _, second = self.start_server('rild1', permissions=0o710)
        _, unrelated = self.start_server('rild2', permissions=0o700)
        self.start_watcher()
        time.sleep(1.4)
        self.assertEqual(mode(first), 0o600)
        self.assertEqual(mode(second), 0o710)
        self.assertEqual(mode(unrelated), 0o700)
        self.assertGreaterEqual(self.log().count('reason=unexpected-mode'), 2)

    def test_idempotent_and_producer_umask_remains_077(self):
        _, path = self.start_server()
        self.start_watcher()
        self.wait_repaired(path)
        result = self.client(path, request='create-file')
        self.assertEqual(result.stdout.strip(), 'CREATED')
        probe = Path(str(path) + '.umask-probe')
        self.assertEqual(mode(probe), 0o600)
        time.sleep(1.4)
        self.assertEqual(mode(probe), 0o600)
        self.assertEqual(self.log().count('repair-ok name=rild0 '), 1)

    def test_real_inotify_queue_overflow_rescans_dropped_target(self):
        maximum = int(Path('/proc/sys/fs/inotify/max_queued_events').read_text().strip())
        count = maximum + 256
        if count > OPTIONS.max_overflow_files:
            self.skipTest('Kernel queue needs %d files; configured test limit is %d; no sysctl changed' %
                          (count, OPTIONS.max_overflow_files))
        self.start_watcher()
        os.kill(self.watcher.pid, signal.SIGSTOP)
        status = Path('/proc/%d/status' % self.watcher.pid)
        wait_until(lambda: '\nState:\tT' in '\n' + status.read_text(), message='watcher did not stop')
        try:
            for number in range(count):
                # Different names prevent event coalescing. No global limit changes.
                fd = os.open(self.directory / ('noise-%06d' % number),
                             os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            _, path = self.start_server('rild1')
            self.assertEqual(mode(path), 0o700)
        finally:
            os.kill(self.watcher.pid, signal.SIGCONT)
        self.wait_repaired(path)
        wait_until(lambda: 'queue-overflow' in self.log(), timeout=10,
                   message='Kernel did not deliver IN_Q_OVERFLOW; overflow coverage is unproven')
        self.assertEqual(self.client(path).stdout.strip(), 'OK')

    def test_root_identity_is_refused_by_daemon(self):
        completed = subprocess.run([str(self.binary), '--directory', str(self.directory)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=3, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertIn('refusing-unexpected-identity', completed.stderr)


def main():
    global OPTIONS, RESULTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path,
                        default=Path(__file__).resolve().with_name('socket_permission_watcher.cpp'))
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--results-dir', type=Path)
    parser.add_argument('--max-overflow-files', type=int, default=70000)
    OPTIONS = parser.parse_args()
    if not sys.platform.startswith('linux'):
        print('NOT RUN: real AF_UNIX DAC/inotify tests require Linux; exit 77.')
        return 77
    if os.geteuid() != 0:
        print('NOT RUN: harness needs root to drop real child UIDs and create negative ownership fixtures; daemon does not. Exit 77.')
        return 77
    if shutil.which(OPTIONS.cxx) is None:
        print('NOT RUN: native Linux C++ compiler not found; exit 77.')
        return 77
    if OPTIONS.results_dir is not None:
        RESULTS = OPTIONS.results_dir.resolve()
        RESULTS.mkdir(exist_ok=False)
    else:
        RESULTS = Path(tempfile.mkdtemp(prefix='klee-qcril-watcher-results-'))
    os.chmod(RESULTS, 0o755)
    captured = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WatcherIntegration)
    result = unittest.TextTestRunner(stream=captured, verbosity=2).run(suite)
    output = captured.getvalue()
    (RESULTS / 'unittest.log').write_text(output)
    print(output)
    summary = dict(linux_tests_executed=True, android_build_executed=False,
        kernel=os.uname().release, tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors),
        skips=[dict(test=str(test), reason=reason) for test, reason in result.skipped],
        successful=result.wasSuccessful(), results_dir=str(RESULTS))
    (RESULTS / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
