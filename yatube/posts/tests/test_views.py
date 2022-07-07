import shutil
import tempfile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django import forms

from ..models import Comment, Follow, Group, Post

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='author')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='test_description',
        )
        cls.group_2 = Group.objects.create(
            title='Тестовая группа 2',
            slug='test_slug_2',
            description='test_description_2',
        )
        cls.gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.uploaded = SimpleUploadedFile(
            name='small.gif',
            content=cls.gif,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.author,
            group=cls.group,
            text='test_post',
            image=cls.uploaded
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.guest_client = Client()
        self.user = User.objects.create_user(username='user')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.authorized_author = Client()
        self.authorized_author.force_login(self.author)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_page_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list', kwargs={
                'slug': self.group.slug}): 'posts/group_list.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit', kwargs={
                'post_id': self.post.id}): 'posts/create_post.html',
            reverse('posts:post_detail', kwargs={
                'post_id': self.post.id}): 'posts/post_detail.html',
            reverse('posts:profile', kwargs={
                'username': self.author.username}): 'posts/profile.html',
        }
        for reverse_name, template in templates_page_names.items():
            with self.subTest(template=template):
                response = self.authorized_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        response = self.guest_client.get(reverse('posts:index'))
        self.assertIn('page_obj', response.context)
        context = response.context['page_obj'][0]
        self.assertEqual(context.text, self.post.text)
        self.assertEqual(context.author, self.author)
        self.assertEqual(context.group, self.group)
        self.assertEqual(context.image, self.post.image)

    def test_group_list_show_correct_context(self):
        """Шаблон group_list сформирован с правильным контекстом."""
        response = self.guest_client.get(reverse('posts:group_list', kwargs={
            'slug': self.group.slug}))
        self.assertIn('page_obj', response.context)
        context = response.context['page_obj'][0]
        self.assertEqual(context.text, self.post.text)
        self.assertEqual(context.author, self.author)
        self.assertEqual(context.group, self.group)
        self.assertEqual(context.image, self.post.image)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_author.get(reverse('posts:profile', kwargs={
            'username': self.author.username}))
        context = response.context['page_obj'][0]
        self.assertEqual(context.text, self.post.text)
        self.assertEqual(context.author, self.author)
        self.assertEqual(context.group, self.group)
        self.assertEqual(context.image, self.post.image)

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_author.get(
            reverse('posts:post_detail', kwargs={
                'post_id': self.post.id}))
        context = response.context['post']
        self.assertEqual(context.text, self.post.text)
        self.assertEqual(context.author, self.author)
        self.assertEqual(context.image, self.post.image)

    def test_edit_post_show_correct_context(self):
        """Шаблон edit_post сформирован с правильным контекстом."""
        response = self.authorized_author.get(reverse(
            'posts:post_edit', kwargs={'post_id': self.post.id}))

        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
        }

        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_check_post_on_create(self):
        """Проверка, что пост добавляется в index, group_list
         и profile при указании группы.
         """
        pages = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.author}),
        ]
        for page in pages:
            with self.subTest(page=page):
                response = self.authorized_author.get(page)
                self.assertEqual(response.context.get('page_obj')[0],
                                 self.post, f'{self.post.id}')

    def test_post_in_group(self):
        """Проверка, что пост не находится в другой группе."""
        response = self.authorized_author.get(
            reverse('posts:group_list', kwargs={'slug': self.group_2.slug}))
        self.assertEqual(len(response.context['page_obj']), 0)

    def test_index_cache_context(self):
        """Проверка, что кеш работает на главной странице"""
        response1 = self.authorized_client.get(reverse("posts:index"))
        Post.objects.create(
            author=self.user,
            text=self.post.text,
        )
        response2 = self.authorized_client.get(reverse("posts:index"))
        self.assertEqual(response1.content, response2.content)
        cache.clear()
        response3 = self.authorized_client.get(reverse("posts:index"))
        self.assertNotEqual(response1.content, response3.content)


class PaginatorViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='Author')
        cls.authorized_author = Client()
        cls.authorized_author.force_login(cls.author)
        cls.group = Group.objects.create(
            title='Тестовая группа 3',
            slug='test-slug_3',
            description='test_description_3',
        )
        cls.page_obj = []

        for i in range(13):
            cls.page_obj.append(
                Post(
                    author=cls.author,
                    text=f'{i} test_text',
                    group=cls.group,
                )
            )
        cls.posts = Post.objects.bulk_create(cls.page_obj)

    def test_first_page_contains_ten_records(self):
        """Первая страница index содержит десять записей."""
        response = self.authorized_author.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_second_page_contains_three_records(self):
        """Вторая страница index содердит три записи."""
        response = self.authorized_author.get(
            reverse('posts:index') + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_group_list_first_page_contains_ten_records(self):
        """Первая страница group_list содержит десять записей.."""
        response = self.authorized_author.get(
            reverse('posts:group_list', kwargs={
                    'slug': self.group.slug}))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_group_list_second_page_contains_three_records(self):
        """Вторая страница group_list содердит три записи."""
        response = self.authorized_author.get(
            reverse('posts:group_list', kwargs={
                    'slug': self.group.slug}) + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)

    def test_profile_first_page_contains_ten_records(self):
        """Первая страница profile содержит десять записей."""
        response = self.authorized_author.get(reverse('posts:profile', kwargs={
            'username': self.author.username}))
        self.assertEqual(len(response.context['page_obj']), 10)

    def test_profile_second_page_contains_three_records(self):
        """Вторая страница profile содердит три записи."""
        response = self.authorized_author.get(reverse('posts:profile', kwargs={
            'username': self.author.username}) + '?page=2')
        self.assertEqual(len(response.context['page_obj']), 3)


class ComentTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='Comments')
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)
        cls.group_test = Group.objects.create(
            title='Тестовая группа',
            slug='test',
            description='Описание тестовой группы'
        )
        cls.post_test = Post.objects.create(
            text='Тестовый пост контент',
            group=cls.group_test,
            author=cls.user,
        )
        cls.comment_test = Comment.objects.create(
            text='Тестовый комментарий',
            post=cls.post_test,
            author=cls.user
        )

    def test_comment_add_on_page(self):
        """Проверка что комментарий добавился к посту."""
        post_id = self.post_test.pk
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': post_id}),
        )
        context = response.context['comments'][0]
        self.assertEqual(context.text, self.comment_test.text)
        self.assertEqual(context.author, self.comment_test.author)


class FollowTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_1 = User.objects.create(username='User')
        cls.user_2 = User.objects.create(username='User_2')
        cls.user_3 = User.objects.create(username='User_3')
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user_1)
        cls.authorized_client_2 = Client()
        cls.authorized_client_2.force_login(cls.user_2)
        cls.group_test = Group.objects.create(
            title='Тестовая группа',
            slug='test',
            description='Описание тестовой группы'
        )
        cls.post_test = Post.objects.create(
            text='Тестовый пост контент',
            group=cls.group_test,
            author=cls.user_2,
        )
        cls.test_follow = Follow.objects.create(
            user=cls.user_1,
            author=cls.user_2
        )

    def test_profile_follow(self):
        """Проверяем что пользователь может подписаться."""
        follow_count = Follow.objects.count()
        username = self.user_3.username
        self.authorized_client.get(reverse(
            'posts:profile_follow',
            kwargs={'username': username}
        ))
        self.assertEqual(Follow.objects.count(), follow_count + 1)
        new_follow = Follow.objects.last()
        self.assertEqual(new_follow.user, self.user_1)
        self.assertEqual(new_follow.author, self.user_3)

    def test_profile_unfollow(self):
        """Проверяем что пользователь может отписаться."""
        follow_count = Follow.objects.count()
        username = self.user_2.username
        self.authorized_client.get(reverse(
            'posts:profile_unfollow',
            kwargs={'username': username}
        ))
        self.assertEqual(Follow.objects.count(), follow_count - 1)

    def test_add_post_in_follower(self):
        """Проверяем что пост появляется в ленте у тех, кто подписан."""
        Follow.objects.create(
            user=self.user_1,
            author=self.user_3,
        )
        new_post = Post.objects.create(
            text='Тестовый пост контент новый',
            group=self.group_test,
            author=self.user_3,
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        first = response.context['page_obj'][0]
        self.assertEqual(first.text, new_post.text)

    def test_no_add_post_in_follower(self):
        """Проверяем что пост не появляется в ленте у тех, кто
        не подписан."""
        posts = Post.objects.filter(author=self.user_2).count()
        Post.objects.create(
            text='Тестовый пост контент новый',
            group=self.group_test,
            author=self.user_3,
        )
        response = self.authorized_client.get(reverse('posts:follow_index'))
        count_posts = len(response.context['page_obj'])
        self.assertEqual(count_posts, posts)
