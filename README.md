# Блогикум — спринт 4

Финальная версия учебного Django-проекта. Основа перенесена из
`dydyvany11-max/django_sprint3`, шаблоны и зависимости взяты из этого
стартового репозитория sprint 4. Готовые HTML-шаблоны перенесены в
`blogicum/templates/` без изменений.

Реализованы регистрация и профиль, редактирование профиля, встроенные
страницы входа и управления паролем, публикации с изображениями,
отложенная публикация, комментарии, редактирование и удаление своего
контента с подтверждением. На главной, в категории и профиле — по
10 записей на страницу и количество комментариев.

Автор видит свои скрытые и будущие посты в профиле и по прямой ссылке;
остальным доступны только опубликованные посты открытых категорий,
дата которых уже наступила. Управлять записью или комментарием может
только его автор. Категории и места создаются через админку.

Статические страницы используют CBV. Настроены страницы 403 CSRF,
404 и 500; последние две отображаются при `DEBUG = False`.
Письма восстановления пароля сохраняются в `blogicum/sent_emails/`.
Медиа, база данных, письма и виртуальное окружение исключены из Git.

## Запуск в Windows (PowerShell)

Из корня `django-sprint4` с Python 3.10 или новее:

```powershell
py -3.10 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe blogicum\manage.py migrate
.\venv\Scripts\python.exe blogicum\manage.py loaddata db.json
.\venv\Scripts\python.exe blogicum\manage.py runserver
```

Загрузка `db.json` необязательна и нужна только для демонстрационных
публикаций. Сайт: http://127.0.0.1:8000/. Для доступа к админке создайте
своего администратора:

```powershell
.\venv\Scripts\python.exe blogicum\manage.py createsuperuser
```

## Проверки

```powershell
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe -m flake8 blogicum
.\venv\Scripts\python.exe blogicum\manage.py check
.\venv\Scripts\python.exe blogicum\manage.py makemigrations --check --dry-run
```

В `tests/test_project_regressions.py` добавлены проверки безопасности:
несовпадение идентификаторов поста и комментария, подмена автора и прав,
защита скрытых публикаций, отсутствие удаления по GET, CSRF,
регистрация, выход и полный сброс пароля через файловый почтовый бэкенд.
Исходные тесты Практикума не изменялись.
