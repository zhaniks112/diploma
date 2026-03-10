from django.contrib.auth.models import User
from django.db import models
from django.conf import settings

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)          # например: "bi bi-lightbulb" для Bootstrap Icons
    order = models.PositiveSmallIntegerField(default=0)         # для сортировки в выпадающем списке

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
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
    STATUS_DONE = 'done'

    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, str(i)) for i in range(1, 6)],
        verbose_name="Оценка качества решения",
        help_text="Оцените от 1 до 5, как была решена проблема"
    )
    rated_at = models.DateTimeField(null=True, blank=True)
    rated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rated_problems'
    )

    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE, 'Done'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,  # или PROTECT, если не хочешь удалять проблемы при удалении категории
        null=True,
        blank=True,
        verbose_name="Категория",
        related_name="problems"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    image = models.ImageField(upload_to='problem_images/', null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='problems', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.status})"

    review_text = models.TextField(
        blank=True,
        verbose_name="Отзыв",
        help_text="Ваш комментарий к оценке (необязательно)"
    )

    resolved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_problems',
        verbose_name="Решил проблему",
        help_text="Сотрудник, который перевёл заявку в resolved/closed"
    )

class StatusHistory(models.Model):
    problem = models.ForeignKey(Problem, related_name='status_history', on_delete=models.CASCADE)
    old_status = models.CharField(max_length=20, choices=Problem.STATUS_CHOICES)
    new_status = models.CharField(max_length=20, choices=Problem.STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='statushistory'  # ← вот это важно!
    )
    def __str__(self):
        return f"{self.problem.title}: {self.old_status} -> {self.new_status} at {self.changed_at}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    problem = models.ForeignKey('Problem', on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.message[:50]}"