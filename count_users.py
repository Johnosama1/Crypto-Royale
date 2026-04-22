cd /root/py2

cat > count_users.py <<'PY'
import json
from pathlib import Path

DATA_FILE = Path('data.json')

if not DATA_FILE.exists():
    print("data.json غير موجود")
    raise SystemExit(1)

with DATA_FILE.open(encoding='utf-8') as f:
    data = json.load(f)

# يغطي حالتين شائعتين: list أو dict
if isinstance(data, list):
    print("عدد المستخدمين (list):", len(data))
elif isinstance(data, dict):
    print("عدد المستخدمين (dict):", len(data.keys()))
else:
    # لو شكل غير متوقع: نحاول حساب المفاتيح أو العناصر الفريدة
    try:
        print("عدد العناصر:", len(data))
    except Exception as e:
        print("شكل data.json غير متوقع:", type(data).__name__, str(e))
PY
