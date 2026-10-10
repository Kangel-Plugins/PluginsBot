import io
import os
import sys
import tarfile
import getpass
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from PluginsBot.utils.backup_utils import decrypt_bytes


def _extract(raw, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)
    return dest


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1]).expanduser()
    dest = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path.cwd() / "kpm_backup_restore"
    if not src.exists():
        print(f"❌ Архив не найден: {src}")
        sys.exit(1)

    blob = src.read_bytes()
    if blob[:6] == b"KPMBK1":
        password = os.getenv("KEY_BACKUP_PASSWORD") or getpass.getpass("Пароль архива: ")
        try:
            blob = decrypt_bytes(blob, password)
        except Exception as e:
            print(f"❌ Не удалось расшифровать (неверный пароль?): {e}")
            sys.exit(1)
    else:
        print("ℹ️ Архив не зашифрован")

    out = _extract(blob, dest)
    print(f"✅ Распаковано: {out}")
    for p in sorted(out.rglob("*")):
        if p.is_file():
            print(f"   {p.relative_to(out)}  ({p.stat().st_size} Б)")


if __name__ == "__main__":
    main()
