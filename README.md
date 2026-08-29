# PluginsBot

Telegram-бот для управления репозиторием на базе [KPM Store](https://github.com/KangelPlugins/Plugins-Store) 


## Требования

- Python 3.10+
- Git с SSH-доступом к репозиторию магазина
- SSH-ключ, добавленный в аккаунт GitHub (бот пушит через SSH)
- Токен Telegram-бота
- Telegram-группа с топиками (форум) для отправки плагинов
- Telegram-канал/топик для уведомлений об обновлениях

### Настройка SSH-ключа

Бот пушит коммиты через SSH. Убедись, что:

1. У тебя есть пара SSH-ключей (`~/.ssh/id_ed25519` или `~/.ssh/id_rsa`).
2. Публичный ключ добавлен в аккаунт GitHub ([Settings > SSH keys](https://github.com/settings/keys)).
3. Ключ загружен в ssh-agent:
   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_ed25519
   ```
4. Проверь подключение:
   ```bash
   ssh -T git@github.com
   ```

## Установка

```bash
cd PluginsBot
git clone <your repo>
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
```

## Конфигурация

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
nano .env
```

## Запуск

Из директории `PluginsBot/`:

```bash
python3 -m bot_plugins
```

Или из корня репозитория:

```bash
cd ..
python3 -m bot_plugins
```


## Лицензия

GPL-3.0 — см. [LICENSE](LICENSE).
