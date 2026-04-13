from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Название"))
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name=_("Описание"))
    icon = models.CharField(max_length=50, blank=True, verbose_name=_("Иконка"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Порядок"))

    class Meta:
        verbose_name = _("Категория")
        verbose_name_plural = _("Категории")
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Problem(models.Model):
    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESOLVED = 'resolved'      # рекомендуется заменить 'done' на 'resolved'
    STATUS_CLOSED = 'closed'

    STATUS_CHOICES = [
        (STATUS_NEW, _('Новый')),
        (STATUS_IN_PROGRESS, _('В работе')),
        (STATUS_RESOLVED, _('Решено')),
        (STATUS_CLOSED, _('Закрыто')),
    ]

    title = models.CharField(max_length=200, verbose_name=_("Название"))
    description = models.TextField(verbose_name=_("Описание"))

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=False,
        blank=False,
        verbose_name=_("Категория"),
        related_name="problems"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        verbose_name=_("Статус")
    )

    image = models.ImageField(
        upload_to='problem_images/',
        null=True,
        blank=True,
        verbose_name=_("Изображение")
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='problems',
        on_delete=models.CASCADE,
        verbose_name=_("Автор")
    )

    assigned_to = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_problems',
        verbose_name=_("Ответственный сотрудник"),
        help_text=_("Сотрудник, назначенный на выполнение заявки")
    )

    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Дата назначения"))

    resolved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_problems',
        verbose_name=_("Решил проблему"),
        help_text=_("Сотрудник, который перевёл заявку в resolved/closed")
    )

    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
        verbose_name=_("Оценка качества решения"),
        help_text=_("Оцените от 1 до 5, как была решена проблема")
    )

    review_text = models.TextField(
        blank=True,
        verbose_name=_("Отзыв"),
        help_text=_("Ваш комментарий к оценке (необязательно)")
    )

    rated_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Дата оценки"))
    rated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rated_problems',
        verbose_name=_("Оценил")
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Дата обновления"))
    last_updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Последнее обновление"))

    class Meta:
        verbose_name = _("Заявка")
        verbose_name_plural = _("Заявки")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class StatusHistory(models.Model):
    problem = models.ForeignKey(Problem, related_name='status_history', on_delete=models.CASCADE)
    old_status = models.CharField(max_length=20, choices=Problem.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Problem.STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='statushistory'
    )

    class Meta:
        verbose_name = _("История изменения статуса")
        verbose_name_plural = _("Истории изменения статусов")
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.problem.title}: {self.old_status} → {self.new_status}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField(verbose_name=_("Сообщение"))
    is_read = models.BooleanField(default=False, verbose_name=_("Прочитано"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))
    problem = models.ForeignKey(
        Problem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )

    class Meta:
        verbose_name = _("Уведомление")
        verbose_name_plural = _("Уведомления")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.message[:50]}"