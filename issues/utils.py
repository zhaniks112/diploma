from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings


def send_status_change_email(problem, new_status):
    """Отправка email автору при смене статуса"""
    if not problem.author.email:
        return  # если у автора нет email — пропускаем

    subject = f"Изменён статус вашей заявки «{problem.title}»"
    message = (
        f"Здравствуйте, {problem.author.username}!\n\n"
        f"Ваша заявка «{problem.title}» изменила статус на «{new_status}».\n"
        f"Перейти к заявке: {settings.BASE_URL}/{problem.pk}/\n\n"
        f"С уважением,\nСервис Университетские проблемы"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[problem.author.email],
        fail_silently=True,  # не падает, если ошибка
    )


def send_new_problem_email(problem):
    """Отправка email персоналу о новой заявке"""
    staff_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
    staff_emails = [email for email in staff_emails if email]  # убираем пустые

    if not staff_emails:
        return

    subject = f"Новая заявка в университете: {problem.title}"
    message = (
        f"Появилась новая заявка!\n\n"
        f"Автор: {problem.author.username}\n"
        f"Категория: {problem.category}\n"
        f"Заголовок: {problem.title}\n"
        f"Описание: {problem.description[:200]}...\n\n"
        f"Ссылка: {settings.BASE_URL}/{problem.pk}/"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=staff_emails,
        fail_silently=True,
    )