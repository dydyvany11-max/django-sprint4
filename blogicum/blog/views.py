from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import CreateView, UpdateView

from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Comment, Post

User = get_user_model()
POSTS_PER_PAGE = 10


def publication_filter():
    return Q(
        is_published=True,
        pub_date__lte=timezone.now(),
        category__is_published=True,
    )


def post_list(queryset):
    return queryset.select_related(
        'author', 'category', 'location',
    ).annotate(comment_count=Count('comments')).order_by('-pub_date', '-pk')


def paginate(request, queryset):
    paginator = Paginator(queryset, POSTS_PER_PAGE)
    return paginator.get_page(request.GET.get('page'))


def visible_post(request, post_id):
    condition = publication_filter()
    if request.user.is_authenticated:
        condition |= Q(author=request.user)
    return get_object_or_404(
        Post.objects.select_related('author', 'category', 'location').filter(
            condition,
        ),
        pk=post_id,
    )


def index(request):
    posts = post_list(Post.objects.filter(publication_filter()))
    return render(request, 'blog/index.html', {
        'page_obj': paginate(request, posts),
    })


def detail_context(post, form=None):
    return {
        'post': post,
        'form': form if form is not None else CommentForm(),
        'comments': post.comments.select_related('author'),
    }


def post_detail(request, post_id):
    post = visible_post(request, post_id)
    return render(request, 'blog/detail.html', detail_context(post))


def category_posts(request, category_slug):
    category = get_object_or_404(
        Category, slug=category_slug, is_published=True,
    )
    posts = post_list(category.posts.filter(publication_filter()))
    return render(request, 'blog/category.html', {
        'category': category,
        'page_obj': paginate(request, posts),
    })


def profile(request, username):
    user = get_object_or_404(User, username=username)
    posts = user.posts.all()
    if request.user != user:
        posts = posts.filter(publication_filter())
    return render(request, 'blog/profile.html', {
        'profile': user,
        'page_obj': paginate(request, post_list(posts)),
    })


class RegistrationView(CreateView):
    form_class = UserCreationForm
    template_name = 'registration/registration_form.html'
    success_url = reverse_lazy('login')


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user.username,))


@login_required
@require_http_methods(['GET', 'POST'])
def create_post(request):
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES or None,
    )
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post.pk)
    form = PostForm(
        request.POST if request.method == 'POST' else None,
        request.FILES or None, instance=post,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post.pk)
    return render(request, 'blog/create.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.author != request.user:
        return redirect('blog:post_detail', post_id=post.pk)
    if request.method == 'POST':
        post.delete()
        return redirect('blog:profile', username=request.user.username)
    return render(request, 'blog/create.html', {
        'form': PostForm(instance=post),
    })


@login_required
@require_POST
def add_comment(request, post_id):
    post = visible_post(request, post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
        return redirect('blog:post_detail', post_id=post.pk)
    return render(request, 'blog/detail.html', detail_context(post, form))


@login_required
@require_http_methods(['GET', 'POST'])
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    form = CommentForm(
        request.POST if request.method == 'POST' else None, instance=comment,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {
        'form': form, 'comment': comment,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id, post_id=post_id)
    if comment.author != request.user:
        return redirect('blog:post_detail', post_id=post_id)
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    return render(request, 'blog/comment.html', {'comment': comment})
