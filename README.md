# PluginsBot

Telegram-бот для управления репозиторием на базе [KPM Store](https://git.kangel.xyz/KangelPlugins/Plugins-Store) 


## Требования

- Python 3.10+
- Git с SSH-доступом к репозиторию магазина
- SSH-ключ, добавленный в Gitea (бот пушит через SSH)
- Токен Telegram-бота
- Telegram-группа с топиками (форум) для отправки плагинов
- Telegram-канал/топик для уведомлений об обновлениях

### Настройка SSH-ключа

Бот пушит коммиты через SSH. Убедись, что:

1. У тебя есть пара SSH-ключей (`~/.ssh/id_ed25519` или `~/.ssh/id_rsa`).
2. Публичный ключ добавлен в Gitea ([Settings > SSH keys](https://git.kangel.xyz/user/settings/keys)).
3. Ключ загружен в ssh-agent:
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519
   ```
4. Проверь подключение:
   ```bash
   ssh -T git@git.kangel.xyz
   ```

## Установка

```bash
git clone <your repo>
cd PluginsBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Конфигурация

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
nano .env
```

## Автобэкап ключей и данных

Раз в сутки бот сам присылает **создателю** (`BACKUP_CHAT_ID`) архив с ключами и данными:
`private_key.pem`, `public_key.pem`, `.env`, `store.json` (+ всё, что перечислишь в `BACKUP_INCLUDE`).
Если задан `KEY_BACKUP_PASSWORD` — архив шифруется **AES-256 ZIP** и открывается обычным
**7-Zip / WinRAR / Keka** по паролю (Python на приёмной стороне не нужен).

Настройки в `.env`:
```
BACKUP_ENABLED=1
BACKUP_CHAT_ID=<твой telegram user id>
BACKUP_INTERVAL_HOURS=24
KEY_BACKUP_PASSWORD=<пароль шифрования архива>
BACKUP_INCLUDE=<доп. пути через запятую, опционально>
```

Ручной запуск в любой момент — команда `/backup` в личке боту.

Открыть архив: в 7-Zip/WinRAR выбрать `kpm-backup-*.zip` → ввести `KEY_BACKUP_PASSWORD`.
Резервный способ (без сторонних утилит) — скриптом:
```bash
KEY_BACKUP_PASSWORD=<пароль> python3 scripts/decrypt_backup.py kpm-backup-XXXX.zip ./restore
```

> ⚠️ Без `KEY_BACKUP_PASSWORD` архив уходит **в открытом виде** (ключ окажется в облаке Telegram).
> Всегда задавай пароль и храни его отдельно от архива.

## Запуск

Из корня репозитория (родительской директории `PluginsBot/`):

```bash
python3 -m PluginsBot
```

## Отправка плагинов

Плагины можно отправить двумя способами:

- **В личные сообщения боту** — бот проверит подписку на канал, предложит выбрать категорию и отправит заявку в группу на рассмотрение.
- **Напрямую в группу** — бот обработает файл и создаст карточку с кнопками «Принять / Отклонить».


## Лицензия

GPL-3.0 — см. [LICENSE](LICENSE).
