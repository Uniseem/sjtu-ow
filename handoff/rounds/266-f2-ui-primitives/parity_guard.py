"""A misspelled selection must fail before any services or data are touched."""
import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("ow_parity", ROOT / "e2e/parity/parity.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with patch.object(m.shutil, 'rmtree') as remove, patch.object(m, 'SHOTS') as shots, patch.object(m, 'prepare_legacy', side_effect=AssertionError('unexpected service setup')):
    assert m.main(['--only=definitely-missing', '--strict']) == 2
    remove.assert_not_called()
    shots.mkdir.assert_not_called()
    assert m.main(['--only=', '--strict']) == 2
    remove.assert_not_called()
    shots.mkdir.assert_not_called()
print('PARITY-EMPTY-SELECTION-GUARD-OK')

if '--mutate' in sys.argv:
    target = ROOT / 'e2e/parity/parity.py'
    original = target.read_text()
    try:
        assert 'if not pages:' in original
        target.write_text(original.replace('if not pages:', 'if False:'))
        result = subprocess.run([sys.executable, __file__], capture_output=True, text=True)
        assert result.returncode != 0 and 'unexpected service setup' in result.stderr, result.stderr
        print('CAUGHT empty selection treated as success')
    finally:
        target.write_text(original)
