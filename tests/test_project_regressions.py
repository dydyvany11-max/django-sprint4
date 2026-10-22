import re
from datetime import timedelta
from importlib import import_module

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import clear_url_caches, path
from django.utils import timezone

from blog.models import Category, Comment, Post

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def content():
    owner = User.objects.create_user('owner', password='test-pass-4729')
    visitor = User.objects.create_user('visitor', password='test-pass-4730')
    category = Category.objects.create(title='Категория', slug='category')
    post = Post.objects.create(
        title='Публикация', text='Текст', author=owner, category=category,
        pub_date=timezone.now() - timedelta(days=1),
    )
    other_post = Post.objects.create(
        title='Другая публикация', text='Текст', author=visitor,
        category=category, pub_date=timezone.now() - timedelta(days=1),
    )
    comment = Comment.objects.create(text='Комментарий', author=owner, post=post)
    return owner, visitor, post, other_post, comment


@pytest.mark.parametrize('operation', ['edit_comment', 'delete_comment'])
def test_comment_must_belong_to_post(client, content, operation):
    owner, _, _, other_post, comment = content
    client.force_login(owner)
    url = f'/posts/{other_post.pk}/{operation}/{comment.pk}/'
    assert client.get(url).status_code == 404
    assert client.post(url, {'text': 'Подмена'}).status_code == 404
    comment.refresh_from_db()
    assert comment.text == 'Комментарий'


@pytest.mark.parametrize('kind', ['future', 'unpublished', 'hidden_category'])
def test_other_users_cannot_comment_on_hidden_posts(client, content, kind):
    owner, visitor, post, _, _ = content
    if kind == 'future':
        post.pub_date = timezone.now() + timedelta(days=1)
    elif kind == 'unpublished':
        post.is_published = False
    else:
        post.category.is_published = False
        post.category.save()
    post.save()
    url = f'/posts/{post.pk}/comment/'
    client.force_login(visitor)
    assert client.post(url, {'text': 'Нельзя'}).status_code == 404
    client.force_login(owner)
    assert client.post(url, {'text': 'Можно'}).status_code == 302
    assert not post.comments.filter(text='Нельзя').exists()
    assert post.comments.filter(text='Можно').exists()


def test_post_author_cannot_edit_someone_elses_comment(client, content):
    owner, visitor, post, _, _ = content
    comment = Comment.objects.create(text='Чужой', author=visitor, post=post)
    client.force_login(owner)
    for operation in ('edit_comment', 'delete_comment'):
        response = client.post(
            f'/posts/{post.pk}/{operation}/{comment.pk}/', {'text': 'Подмена'},
        )
        assert response.status_code == 302
        comment.refresh_from_db()
        assert comment.text == 'Чужой'


def test_get_does_not_delete_content(client, content):
    owner, _, post, _, comment = content
    client.force_login(owner)
    assert client.get(f'/posts/{post.pk}/delete/').status_code == 200
    response = client.get(
        f'/posts/{post.pk}/delete_comment/{comment.pk}/',
    )
    assert response.status_code == 200
    assert Post.objects.filter(pk=post.pk).exists()
    assert Comment.objects.filter(pk=comment.pk).exists()


def test_post_form_ignores_forged_owner_and_publication_status(client, content):
    owner, visitor, post, _, _ = content
    client.force_login(owner)
    response = client.post('/posts/create/', {
        'title': 'Новый', 'text': 'Текст', 'pub_date': '2030-01-01T12:00',
        'category': post.category_id, 'author': visitor.pk,
        'is_published': False,
    })
    assert response.status_code == 302
    created = Post.objects.get(title='Новый')
    assert created.author == owner
    assert created.is_published


def test_empty_post_form_displays_validation_errors(client, content):
    client.force_login(content[0])
    response = client.post('/posts/create/', {})
    assert response.context['form'].is_bound
    assert 'title' in response.context['form'].errors


def test_registration_and_logout(client):
    response = client.post('/auth/registration/', {
        'username': 'new-reader', 'password1': 'sample-pass-387492',
        'password2': 'sample-pass-387492',
    })
    assert response.status_code == 302
    assert response.url == '/auth/login/'
    assert client.login(username='new-reader', password='sample-pass-387492')
    assert client.post('/auth/logout/').status_code == 200
    assert '_auth_user_id' not in client.session


def test_profile_cannot_grant_staff_permissions(client, content):
    owner = content[0]
    client.force_login(owner)
    response = client.post('/edit_profile/', {
        'username': 'new-owner', 'first_name': 'Имя', 'last_name': 'Фамилия',
        'email': 'owner@example.com', 'is_staff': True, 'is_superuser': True,
    })
    owner.refresh_from_db()
    assert response.status_code == 302
    assert response.url == '/profile/new-owner/'
    assert owner.first_name == 'Имя'
    assert not owner.is_staff
    assert not owner.is_superuser


def test_password_reset_writes_usable_link_to_file(client, settings, tmp_path):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    settings.EMAIL_FILE_PATH = tmp_path
    user = User.objects.create_user(
        'reader', email='reader@example.com', password='old-pass-934829',
    )
    response = client.post('/auth/password_reset/', {
        'email': user.email,
    })
    assert response.status_code == 302
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    message = files[0].read_text(encoding='utf-8')
    reset_path = re.search(r'http://testserver(/auth/reset/[^\s]+)', message)
    assert reset_path is not None
    response = client.get(reset_path.group(1))
    assert response.status_code == 302
    response = client.post(response.url, {
        'new_password1': 'new-password-825739',
        'new_password2': 'new-password-825739',
    })
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password('new-password-825739')


def test_csrf_rejection_uses_custom_page():
    response = Client(enforce_csrf_checks=True).post('/auth/login/', {})
    assert response.status_code == 403
    assert 'pages/403csrf.html' in [t.name for t in response.templates]


def test_server_error_uses_custom_page(client, settings, monkeypatch):
    def broken_view(request):
        raise RuntimeError('Test error')

    settings.DEBUG = False
    module = import_module(settings.ROOT_URLCONF)
    monkeypatch.setattr(
        module, 'urlpatterns', module.urlpatterns + [path('crash/', broken_view)],
    )
    client.raise_request_exception = False
    clear_url_caches()
    try:
        response = client.get('/crash/')
    finally:
        clear_url_caches()
    assert response.status_code == 500
    assert 'pages/500.html' in [t.name for t in response.templates]
