import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Comment, Group, Post


User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp()


class CommentFormTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username='Comments')
        cls.guest_client = Client()
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

    def test_authorized_comment_add(self):
        """Проверка что авторизованный пользователь может добавить
        комментарий.
        """
        comments_count = Comment.objects.count()
        post_id = self.post_test.pk
        form_data = {
            'text': 'Тестовый комментарий 2'
        }
        self.authorized_client.post(
            reverse('posts:add_comment', kwargs={'post_id': post_id}),
            data=form_data
        )
        self.assertEqual(Comment.objects.count(), comments_count + 1)

    def test_guest_comment_add(self):
        """Проверка что гостевой пользователь не может добавить
        комментарий.
        """
        comments_count = Comment.objects.count()
        post_id = self.post_test.pk
        form_data = {
            'text': 'Тестовый комментарий 2'
        }
        response = self.guest_client.post(
            reverse('posts:add_comment', kwargs={'post_id': post_id}),
            data=form_data
        )
        self.assertEqual(Comment.objects.count(), comments_count)
        redirect = "%s?next=%s" % (
            reverse('users:login'),
            reverse('posts:add_comment', kwargs={'post_id': post_id})
        )
        self.assertRedirects(response, redirect)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.author = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test_slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.author,
            text='Тестовый пост для тестирования',
            group=cls.group
        )
        cls.gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(self.author)

    def test_create_post(self):
        """Валидная форма создания поста с гифкой."""
        posts_count = Post.objects.count()
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=self.gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'текст',
            'author': self.author,
            'group': self.group.id,
            'image': uploaded
        }
        response = self.authorized_client.post(reverse('posts:post_create'),
                                               data=form_data, follow=True)
        self.assertRedirects(response,
                             reverse('posts:profile',
                                     kwargs={'username':
                                             self.author.username}))
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertTrue(Post.objects.filter(text='текст',
                                            author=self.author).exists())
        self.assertEqual(response.context['page_obj'].object_list[0].image,
                         'posts/small.gif')

    def test_edit_post(self):
        """Валидная форма редактировани поста."""
        posts_count = Post.objects.count()
        form_data = {
            'text': 'отредактированный текст',
            'group': self.group.id,
        }
        response = self.authorized_client.post(
            reverse(('posts:post_edit'),
                    kwargs={'post_id': self.post.id}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse('posts:post_detail', args=(1,)))
        self.assertEqual(Post.objects.count(), posts_count)
        self.assertTrue(
            Post.objects.filter(
                text='отредактированный текст',
                group=self.group.id,
            ).exists()
        )
