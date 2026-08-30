#!/usr/bin/env python3
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
bot_dir = os.path.dirname(script_dir)
project_dir = os.path.dirname(bot_dir)
sys.path.insert(0, project_dir)

from PluginsBot.utils.crypto_utils import generate_key_pair


def main():
    repo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    private_key_path = os.path.join(repo_path, "private_key.pem")
    public_key_path = os.path.join(repo_path, "public_key.pem")

    if os.path.exists(private_key_path):
        print(f"⚠️ Приватный ключ уже существует: {private_key_path}")
        resp = input("Перезаписать? (y/n): ").strip().lower()
        if resp != 'y':
            return

    private_key, public_key = generate_key_pair()

    with open(private_key_path, "wb") as f:
        f.write(private_key)
    os.chmod(private_key_path, 0o600)

    with open(public_key_path, "wb") as f:
        f.write(public_key)

    print(f"✅ Приватный ключ: {private_key_path}")
    print(f"✅ Публичный ключ: {public_key_path}")
    print("\n⚠️ Добавьте в .env:")
    print(f"PRIVATE_KEY_PATH={private_key_path}")

if __name__ == "__main__":
    main()
