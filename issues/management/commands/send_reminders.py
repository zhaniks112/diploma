from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from issues.models import Problem


class Command(BaseCommand):
    help = 'Отправляет индивидуальные напоминания ответственным за зависшие заявки'

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(days=3)   # 3 дня без изменений

        # Получаем все зависшие заявки
        overdue_problems = Problem.objects.filter(
            status__in=['new', 'in_progress'],
            last_updated_at__lt=threshold
        ).select_related('author', 'assigned_to', 'resolved_by')

        if not overdue_problems.exists():
            self.stdout.write(self.style.SUCCESS("Нет зависших заявок."))
            return

        # Группируем заявки по ответственному
        reminders = {}          # email → список заявок
        general_reminders = []  # заявки без ответственного

        for problem in overdue_problems:
            # Приоритет: assigned_to → resolved_by
            responsible = problem.assigned_to or problem.resolved_by

            if responsible and responsible.email:
                email = responsible.email
                if email not in reminders:
                    reminders[email] = []
                reminders[email].append(problem)
            else:
                general_reminders.append(problem)

        # 1. Отправляем индивидуальные письма
        for email, problems in reminders.items():
            responsible = problems[0].assigned_to or problems[0].resolved_by

            subject = f"[{responsible.username}] Напоминание: {len(problems)} зависших заявок"

            message_lines = [f"Здравствуйте, {responsible.get_full_name() or responsible.username}!\n\n"]
            message_lines.append(f"У вас есть {len(problems)} незавершённых заявок, которые не обновлялись более 3 дней:\n\n")

            for p in problems:
                message_lines.append(
                    f"• {p.title} (ID: {p.pk})\n"
                    f"  Статус: {p.status}\n"
                    f"  Автор: {p.author.username}\n"
                    f"  Последнее обновление: {p.last_updated_at.strftime('%d.%m.%Y %H:%M')}\n"
                    f"  Ссылка: {settings.BASE_URL.rstrip('/')}/problems/{p.pk}/\n\n"
                )

            message_lines.append("Пожалуйста, проверьте и обновите статусы.\nС уважением,\nСервис Университетские проблемы")

            send_mail(
                subject=subject,
                message=''.join(message_lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            self.stdout.write(self.style.SUCCESS(
                f"Отправлено письмо на {email} → {responsible.username} ({len(problems)} заявок)"
            ))

        # 2. Общее письмо для заявок без ответственного
        if general_reminders:
            staff_emails = User.objects.filter(is_staff=True).values_list('email', flat=True)
            staff_emails = [e for e in staff_emails if e]

            if staff_emails:
                subject = f"{len(general_reminders)} зависших заявок без ответственного"

                message_lines = ["Здравствуйте, уважаемый персонал!\n\n"]
                message_lines.append("Следующие заявки не имеют назначенного ответственного и не обновлялись более 3 дней:\n\n")

                for p in general_reminders:
                    message_lines.append(
                        f"• {p.title} (ID: {p.pk})\n"
                        f"  Статус: {p.status}\n"
                        f"  Автор: {p.author.username}\n"
                        f"  Последнее обновление: {p.last_updated_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"  Ссылка: {settings.BASE_URL.rstrip('/')}/problems/{p.pk}/\n\n"
                    )

                message_lines.append("Пожалуйста, назначьте ответственных и обновите статусы.\nС уважением,\nСервис Университетские проблемы")

                send_mail(
                    subject=subject,
                    message=''.join(message_lines),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=staff_emails,
                    fail_silently=False,
                )

                self.stdout.write(self.style.SUCCESS(f"Общее напоминание отправлено о {len(general_reminders)} заявках без ответственного"))

        self.stdout.write(self.style.SUCCESS(f'Напоминания обработаны. Всего обработано заявок: {overdue_problems.count()}'))