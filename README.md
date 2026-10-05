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
