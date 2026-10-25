"""Build-time display names; internal single-instance identifiers stay stable."""
import json
from pathlib import Path
_path = Path(__file__).with_name('portable-branding.json')
_values = json.loads(_path.read_text(encoding='utf-8')) if _path.exists() else {}
APP_NAME = _values.get('app_name', 'QuietCapture')
MONITOR_NAME = _values.get('monitor_name', 'QuietCaptureMonitor')
