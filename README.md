# MeetService

Сервис для поиска IT-команды к проектам.

## Локальный запуск

```bash
source venv/bin/activate
python -m pip install -r requirements.txt
cd meetService
python manage.py migrate
python manage.py runserver
```

## Celery

Для фоновых задач нужен Redis.

```bash
cd meetService
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

Периодические задачи:

- истечение старых ожидающих приглашений;
- email-сводка владельцам проектов по ожидающим откликам;
- email-сводка специалистам по ожидающим приглашениям;
- синхронизация счетчиков и статусов открытых ролей проектов.

## Mailhog

Для проверки писем в Docker используется Mailhog:

- SMTP: `mailhog:1025`;
- Web UI: `http://localhost:8025`.

Для локального запуска без Docker можно указать:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=1025
EMAIL_USE_TLS=False
```

## Google OAuth2

В `.env` нужно указать:

```env
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=
```

Redirect URI для Google OAuth:

```text
http://localhost:8000/oauth/google/login/callback/
```

Redirect URI для GitHub OAuth:

```text
http://localhost:8000/oauth/github/login/callback/
```

Если ключи провайдера не заданы, обычный вход продолжает работать, а соответствующая OAuth-кнопка не показывается.

## Docker

Проект в Docker оставляет SQLite основной базой. PostgreSQL не поднимается, но `psycopg` есть в зависимостях для будущего перехода.

```bash
docker compose build
docker compose up
```

После запуска:

- приложение: `http://localhost:8000`;
- Mailhog: `http://localhost:8025`;
- Redis: `localhost:6379`.
