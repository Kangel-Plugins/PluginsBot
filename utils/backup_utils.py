import io
import os
import time
import tarfile
import tempfile
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


def _tar_bytes(paths):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in paths:
            p = Path(p)
            arc = p.name if p.is_file() else p.name
            if p.is_file() and p.parent.name:
                arc = f"{p.parent.name}/{p.name}"
            tar.add(str(p), arcname=arc)
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
    raw = _tar_bytes(paths)
    password = os.getenv("KEY_BACKUP_PASSWORD", "")
    stamp = time.strftime("%Y%m%d-%H%M%S")

    if password:
        blob = encrypt_bytes(raw, password)
        name = f"kpm-backup-{stamp}.tar.gz.enc"
        encrypted = True
    else:
        blob = raw
        name = f"kpm-backup-{stamp}.tar.gz"
        encrypted = False

    tmp = Path(tempfile.gettempdir()) / name
    tmp.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()[:16]
    return {
        "path": tmp,
        "name": name,
        "encrypted": encrypted,
        "files": [str(p) for p in paths],
        "raw_size": len(raw),
        "size": len(blob),
        "sha256": digest,
    }
