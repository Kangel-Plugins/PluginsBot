
import os
import subprocess

from PluginsBot.config import REPO_PATH


def ensure_ssh_remote():
    try:
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=REPO_PATH,
        )

        current_url = remote_result.stdout.strip()

        if current_url.startswith("git@") or current_url.startswith("ssh://"):
            print(f"✅ SSH remote уже настроен: {current_url}")
            return

        if "github.com" in current_url:
            if "github.com/" in current_url:
                repo_path = current_url.split("github.com/")[1].replace(".git", "")
                ssh_url = f"git@github.com:{repo_path}.git"

                print(f"🔄 Переключаю remote с HTTPS на SSH...")
                subprocess.run(
                    ["git", "remote", "set-url", "origin", ssh_url],
                    check=True,
                    cwd=REPO_PATH,
                )
                print(f"✅ Remote переключен на SSH: {ssh_url}")
            else:
                print(f"⚠️ Не удалось определить путь репозитория из URL: {current_url}")
        else:
            print(f"⚠️ Неизвестный формат remote URL: {current_url}")

    except subprocess.CalledProcessError as e:
        print(f"⚠️ Ошибка при настройке SSH remote: {e}")
        print(f"   Продолжаю с текущей конфигурацией...")


def _git_get(repo_path: str, args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        if r.returncode != 0:
            return ""
        return (r.stdout or "").strip()
    except Exception:
        return ""


def check_git_identity(repo_path: str) -> None:
    expected_name = (os.getenv("EXPECTED_GIT_USER_NAME") or "").strip()
    expected_email = (os.getenv("EXPECTED_GIT_USER_EMAIL") or "").strip()

    name = _git_get(repo_path, ["config", "--get", "user.name"])
    email = _git_get(repo_path, ["config", "--get", "user.email"])
    origin = _git_get(repo_path, ["remote", "get-url", "origin"])

    print(f"👤 Git identity: {name or '(no user.name)'} <{email or '(no user.email)'}>")
    if origin:
        print(f"🔗 Git origin: {origin}")

    mismatches = []
    if expected_name and name and name != expected_name:
        mismatches.append(f"user.name '{name}' != '{expected_name}'")
    if expected_email and email and email != expected_email:
        mismatches.append(f"user.email '{email}' != '{expected_email}'")

    if mismatches:
        msg = "❌ Git identity mismatch, aborting commit/push:\n" + "\n".join(mismatches)
        print(msg)
        raise Exception(msg)

def commit_and_push(plugin_id: str, version: str, is_new: bool):
    try:
        os.chdir(REPO_PATH)
        ensure_ssh_remote()
        check_git_identity(REPO_PATH)
        status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        print(f"📊 Git status:\n{status_result.stdout if status_result.stdout else '(нет изменений)'}")
        add_result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        subprocess.run(["git", "add", "store.json"], capture_output=True, text=True)
        if add_result.returncode != 0:
            print(f"❌ Ошибка при git add: {add_result.stderr}")
        else:
            print(f"✅ Git add успешен")

        staged_result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)

        if not staged_result.stdout.strip():
            print(f"⚠️ Нет изменений для коммита (файлы уже закоммичены или не изменены)")
            return False, None

        print(f"📝 Файлы для коммита:\n{staged_result.stdout}")

        if is_new:
            commit_message = f"Add plugin: {plugin_id} v{version}"
        else:
            commit_message = f"Update plugin: {plugin_id} v{version}"

        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True,
        )

        if commit_result.returncode != 0:
            print(f"❌ Ошибка при git commit:")
            print(f"   stdout: {commit_result.stdout}")
            print(f"   stderr: {commit_result.stderr}")
            raise Exception(f"Git commit failed: {commit_result.stderr}")

        print(f"✅ Git коммит успешен: {commit_message}")

        print("🔄 Выполняю git pull...")
        pull_result = subprocess.run(
            ["git", "pull", "origin", "main", "--no-rebase"],
            capture_output=True,
            text=True,
        )

        if pull_result.returncode != 0:
            print(f"⚠️ Предупреждение при git pull: {pull_result.stderr}")
        else:
            print(f"✅ Git pull успешен")

        print("🚀 Выполняю git push...")
        push_result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True,
            text=True)

        if push_result.returncode != 0:
            print(f"❌ Ошибка при git push:")
            print(f"   stdout: {push_result.stdout}")
            print(f"   stderr: {push_result.stderr}")

            if "Permission denied" in push_result.stderr or "Authentication failed" in push_result.stderr:
                print(f"\n💡 Подсказка: Убедитесь, что:")
                print(f"   1. SSH ключ добавлен в ssh-agent: ssh-add ~/.ssh/id_rsa")
                print(f"   2. SSH ключ добавлен в GitHub: https://github.com/settings/keys")
                print(f"   3. Проверьте подключение: ssh -T git@github.com")

            raise Exception(f"Git push failed: {push_result.stderr}")

        print(f"✅ Git пуш успешен")
        return True, commit_message

    except Exception as e:
        print(f"❌ Ошибка при коммите/пуше: {e}")
        raise
