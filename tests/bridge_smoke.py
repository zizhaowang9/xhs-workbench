"""Exercise the shipped bridge and probe over real localhost WebSockets."""
from pathlib import Path
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / 'tools/xiaohongshu-skills/scripts/bridge_server.py'
PROBE = REPO / 'installer/bridge_probe.py'


def assert_server_pid(reported_pid, process):
    assert isinstance(reported_pid, int) and reported_pid > 0, reported_pid
    if reported_pid == process.pid:
        return
    # Windows venv python.exe can be a launcher whose child owns the listener.
    # Accept only a verified descendant of the subprocess we actually launched.
    assert sys.platform == 'win32', (reported_pid, process.pid)
    ancestry = (
        '$currentId = ' + str(reported_pid) + '; '
        'for ($depth = 0; $depth -lt 8 -and $currentId -gt 0; $depth++) { '
        'if ($currentId -eq ' + str(process.pid) + ') { exit 0 }; '
        '$entry = Get-CimInstance Win32_Process -Filter ("ProcessId=" + $currentId); '
        'if (-not $entry) { exit 1 }; $currentId = [int]$entry.ParentProcessId }; exit 1'
    )
    verified = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ancestry],
                              capture_output=True, timeout=10)
    assert verified.returncode == 0, (reported_pid, process.pid, verified.stderr)


def check(server, expected_root, explicit_root=None):
    with socket.socket() as sock:
        sock.bind(('localhost', 0))
        port = sock.getsockname()[1]
    args = [sys.executable, str(server), '--port', str(port)]
    if explicit_root is not None:
        args.extend(['--root', str(explicit_root)])
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(args, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    log.seek(0)
                    raise AssertionError(log.read().decode('utf-8', errors='replace'))
                result = subprocess.run([sys.executable, str(PROBE), '--port', str(port), '--timeout', '0.3'],
                                        capture_output=True, text=True, encoding='utf-8', timeout=5)
                data = json.loads(result.stdout)
                if data['reachable']:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError('Bridge did not answer ping_server')
            assert data['root'] == (str(expected_root.resolve()) if expected_root else None), data
            assert_server_pid(data['pid'], process)
            assert data['script_path'] == str(server.resolve()), data
            assert data['extension'] is False, data
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix='xhs bridge 中文 ') as temporary:
    root = Path(temporary)
    check(SERVER, root, root)
    standalone = root / 'standalone' / 'bridge_server.py'
    standalone.parent.mkdir()
    shutil.copyfile(SERVER, standalone)
    check(standalone, None)  # Legacy --port only must not invent ownership.
    installed = root / 'tools/xiaohongshu-skills/scripts/bridge_server.py'
    installed.parent.mkdir(parents=True)
    shutil.copyfile(SERVER, installed)
    (root / 'config').mkdir()
    (root / 'config/paths.json').write_text('{}', encoding='utf-8')
    check(installed, root)  # Legacy --port in a real installed layout.
print('PASS: explicit root, legacy standalone, installed legacy; real localhost ping identities')
