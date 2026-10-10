#!/usr/bin/env python3
import io
import os
import sys
import shutil
import tarfile
import zipfile
import getpass
import subprocess
import tempfile
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from PluginsBot.utils.backup_utils import decrypt_bytes, MAGIC

ZIP_MAGIC = b"PK\x03\x04"


def _extract_tar(raw, dest):
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def _extract_zip(path, dest, password):
    try:
        import pyzipper
        with pyzipper.AESZipFile(path) as zf:
            if password:
                zf.setpassword(password.encode("utf-8"))
            zf.extractall(dest)
        return
    except ImportError:
        pass
    except RuntimeError as ex:
        raise RuntimeError(f"похоже, нужен пароль (или неверный): {ex}")

    try:
        with zipfile.ZipFile(path) as zf:
            zf.extractall(dest)
        return
    except RuntimeError as ex:
        sevenzip = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        if not sevenzip:
            raise RuntimeError(f"AES-ZIP: нужен pyzipper или 7z ({ex})")
        subprocess.run([sevenzip, "x", f"-p{password or ''}", f"-o{dest}", "-y", str(path)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = Path(sys.argv[1]).expanduser()
    dest = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path.cwd() / "kpm_backup_restore"
    if not src.exists():
        print(f"❌ Архив не найден: {src}")
        sys.exit(1)
    dest.mkdir(parents=True, exist_ok=True)

    blob = src.read_bytes()
    try:
        if blob[:len(MAGIC)] == MAGIC:
            password = os.getenv("KEY_BACKUP_PASSWORD") or getpass.getpass("Пароль архива: ")
            raw = decrypt_bytes(blob, password)
            _extract_tar(raw, dest)
            print("ℹ️ Формат: tar.gz.enc (AES-GCM)")
        elif blob[:4] == ZIP_MAGIC:
            password = os.getenv("KEY_BACKUP_PASSWORD") or getpass.getpass("Пароль архива: ")
            _extract_zip(src, dest, password)
            print("ℹ️ Формат: ZIP" + (" (AES-256)" if password else " (без шифрования)"))
        else:
            _extract_tar(blob, dest)
            print("ℹ️ Формат: tar.gz")
    except Exception as ex:
        print(f"❌ Не удалось распаковать: {ex}")
        sys.exit(1)

    print(f"✅ Распаковано: {dest}")
    for p in sorted(dest.rglob("*")):
        if p.is_file():
            print(f"   {p.relative_to(dest)}  ({p.stat().st_size} Б)")


if __name__ == "__main__":
    main()
