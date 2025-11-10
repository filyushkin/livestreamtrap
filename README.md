# LivestreamTrap

Django веб-приложение для мониторинга и записи YouTube трансляций.

## Функции

- Мониторинг YouTube каналов
- Автоматическая запись живых трансляций
- Конвертация в MP3
- Веб-интерфейс для управления

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение
3. Установите зависимости: `pip install -r requirements.txt`
4. Создайте файл `.env` с настройками
5. Выполните миграции: `python manage.py migrate`
6. Запустите сервер: `python manage.py runserver`

## Запуск

* Запуск через Docker Compose:

docker-compose up --build

* Запуск в Docker + через 3 терминала IDE:

a) Docker Desktop:

docker run -d --name redis-server -p 6379:6379 redis:7-alpine

b) 3 терминала IDE:

python manage.py runserver

celery -A livestreamtrap worker -l info --pool=solo

celery -A livestreamtrap beat -l info
