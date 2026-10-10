import io
import os
import time
import shutil
import tarfile
import zipfile
import tempfile
import subprocess
import hashlib
from pathlib import Path

MAGIC = b"KPMBK1"
KDF_ITERATIONS = 200_000


def collect_paths():
    from PluginsBot import config

    bot_dir = Path(config.__file__).resolve().parent
    paths = []

    def add(p):
        if p is None:
            return
        p = Path(p).expanduser()
        if p.exists():
            paths.append(p)

    priv = Path(getattr(config, "PRIVATE_KEY_PATH", bot_dir / "private_key.pem"))
    add(priv)
    add(priv.with_name("public_key.pem"))
    add(bot_dir / "public_key.pem")
    add(bot_dir / ".env")
    add(bot_dir.parent / ".env")
    try:
        add(Path(config.STORE_JSON_FILE))
    except Exception:
        pass

    for extra in (os.getenv("BACKUP_INCLUDE") or "").split(","):
        extra = extra.strip()
        if extra:
            add(Path(extra))

    seen = set()
    result = []
    for p in paths:
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        result.append(p)
    return result


def _arcnames(paths):
    items = []
    for p in paths:
        p = Path(p)
        name = f"{p.parent.name}/{p.name}" if p.is_file() and p.parent.name else p.name
        items.append((str(p), name))
    return items


def _zip_plain(paths):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in _arcnames(paths):
            zf.write(src, arcname=arc)
    return buf.getvalue()


def _zip_aes(paths, password):
    try:
        import pyzipper
        buf = io.BytesIO()
        with pyzipper.AESZipFile(
            buf, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as zf:
            zf.setpassword(password.encode("utf-8"))
            for src, arc in _arcnames(paths):
                zf.write(src, arcname=arc)
        return buf.getvalue()
    except ImportError:
        return _zip_aes_7z(paths, password)


def _zip_aes_7z(paths, password):
    sevenzip = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
    if not sevenzip:
        raise RuntimeError("нет pyzipper и 7z — AES-ZIP недоступен")
    tmpdir = tempfile.mkdtemp(prefix="kpmbk-")
    try:
        stage = Path(tmpdir) / "stage"
        stage.mkdir()
        for src, arc in _arcnames(paths):
            dest = stage / arc
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        out_zip = Path(tmpdir) / "backup.zip"
        subprocess.run(
            [sevenzip, "a", "-tzip", "-mem=AES256", f"-p{password}", str(out_zip), "."],
            cwd=str(stage),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return out_zip.read_bytes()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _tar_bytes(paths):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for src, arc in _arcnames(paths):
            tar.add(src, arcname=arc)
    return buf.getvalue()


def encrypt_bytes(data, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(16)
    nonce = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    key = kdf.derive(password.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return MAGIC + salt + nonce + ciphertext


def decrypt_bytes(blob, password):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if blob[:len(MAGIC)] != MAGIC:
        return blob
    salt = blob[len(MAGIC):len(MAGIC) + 16]
    nonce = blob[len(MAGIC) + 16:len(MAGIC) + 28]
    ciphertext = blob[len(MAGIC) + 28:]
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=KDF_ITERATIONS)
    key = kdf.derive(password.encode("utf-8"))
    return AESGCM(key).decrypt(nonce, ciphertext, None)


def build_backup():
    paths = collect_paths()
    password = os.getenv("KEY_BACKUP_PASSWORD", "")
    stamp = time.strftime("%Y%m%d-%H%M%S")

    if password:
        try:
            blob = _zip_aes(paths, password)
            name = f"kpm-backup-{stamp}.zip"
            fmt = "zip-aes"
        except Exception as ex:
            print(f"⚠️ AES-ZIP недоступен ({ex}); откат на .tar.gz.enc")
            blob = encrypt_bytes(_tar_bytes(paths), password)
            name = f"kpm-backup-{stamp}.tar.gz.enc"
            fmt = "aesgcm"
    else:
        blob = _zip_plain(paths)
        name = f"kpm-backup-{stamp}.zip"
        fmt = "zip-plain"
        print("⚠️ KEY_BACKUP_PASSWORD не задан — архив БЕЗ шифрования!")

    tmp = Path(tempfile.gettempdir()) / name
    tmp.write_bytes(blob)
    return {
        "path": tmp,
        "name": name,
        "encrypted": bool(password),
        "format": fmt,
        "files": [str(p) for p in paths],
        "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest()[:16],
    }
