# PluginsBot

Telegram-бот для управления репозиторием на базе [KPM Store](https://git.kangel.xyz/KangelPlugins/Plugins-Store) на базе **aiogram 3.x**.


## Требования

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (быстрый менеджер пакетов и виртуальных окружений)
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
uv sync
```

## Конфигурация

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
nano .env
```

## Запуск

Запуск бота осуществляется через `uv`:

```bash
# Обычный запуск:
uv run bot

# Демо-режим (тестирование вёрстки сообщений и интерактивных кнопок):
uv run bot --demo
```

> **Совет**: Если вы активируете виртуальное окружение (`source .venv/bin/activate` на Linux/macOS или `.venv\Scripts\Activate.ps1` на Windows), бот доступен напрямую командой:
> ```bash
> bot
> # или
> bot --demo
> ```

## Автозапуск через systemd

В репозитории лежит готовый юнит `PluginsBot.service`. Установка:

```bash
sudo cp PluginsBot.example.service /etc/systemd/system/PluginsBot.service
sudo systemctl daemon-reload
sudo systemctl enable --now PluginsBot
```

Полезное:

```bash
journalctl -u PluginsBot -f        # живые логи
sudo systemctl restart PluginsBot  # рестарт после git pull (зависимости пересоберутся сами)
sudo systemctl status PluginsBot   # статус
```

> Перед каждым запуском `ExecStartPre` делает `uv sync --upgrade` — пакеты
> ставятся/обновляются до свежих версий, затем стартует бот. После `git pull`
> достаточно перезапустить службу.

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
KEY_BACKUP_PASSWORD=<пароль> uv run scripts/decrypt_backup.py kpm-backup-XXXX.zip ./restore
```

> ⚠️ Без `KEY_BACKUP_PASSWORD` архив уходит **в открытом виде** (ключ окажется в облаке Telegram).
> Всегда задавай пароль и храни его отдельно от архива.

## Отправка плагинов

Плагины можно отправить двумя способами:

- **В личные сообщения боту** — бот проверит подписку на канал, предложит выбрать категорию и отправит заявку в группу на рассмотрение.
- **Напрямую в группу** — бот обработает файл и создаст карточку с кнопками «Принять / Отклонить».


## Лицензия

GPL-3.0 — см. [LICENSE](LICENSE).
