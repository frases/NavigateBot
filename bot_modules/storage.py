import json
from pathlib import Path

def load_json_file(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default

def save_json_file(path_str, data):
    Path(path_str).write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding='utf-8',
    )
