from django.contrib import messages
from django.contrib.auth import login
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, ExpressionWrapper, FloatField, F, When, Value, Case
from django.db.models import Q
import django.db.models as models
from django.contrib.auth.models import User
from .models import Problem, StatusHistory, Category, Notification
from django.shortcuts import render, redirect
from .forms import ProblemForm, RegisterForm, ProblemRatingForm
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from .models import Problem
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

from .utils import send_new_problem_email, send_status_change_email
from django.utils.translation import gettext_lazy as _


@login_required
def problem_list(request):
    problems = Problem.objects.all()

    if request.user.is_staff:
        # Сотрудник видит только свои назначенные заявки + все завершённые
        problems = problems.filter(
            models.Q(assigned_to=request.user) |
            models.Q(status__in=['resolved', 'closed']) |
            models.Q(status='new')
        )
    else:
        # Студент видит только свои заявки
        problems = problems.filter(author=request.user)

    # Фильтры из GET-параметров
    category_id = request.GET.get('category')

    if category_id:
        try:
            category_id = int(category_id)  # приводим к числу
        except (ValueError, TypeError):
            category_id = None

    status = request.GET.get('status')
    search_query = request.GET.get('q')  # поиск по заголовку/описанию
    sort_by = request.GET.get('sort', 'created_at')  # сортировка по умолчанию

    # Фильтр по категории
    if category_id:
        problems = problems.filter(category_id=category_id)

    # Фильтр по статусу
    if status:
        problems = problems.filter(status=status)

    # Поиск по заголовку или описанию
    if search_query:
        problems = problems.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Сортировка
    sort_options = {
        'created_at': '-created_at',           # новые сверху
        'title': 'title',
        '-title': '-title',
        'status': 'status',
        'rating': '-rating',                   # по оценке (лучшие сверху)
    }

    sort_field = sort_options.get(sort_by, '-created_at')
    problems = problems.order_by(sort_field)

    # Все категории для выпадающего списка
    categories = Category.objects.all()

    unread_notifications = 0
    if request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(is_read=False).count()

    # Передаём текущие параметры в шаблон (для сохранения фильтров)
    context = {
        'problems': problems,
        'categories': categories,
        'selected_category': category_id,
        'selected_status': status,
        'search_query': search_query,
        'selected_sort': sort_by,
    }

    return render(request, 'issues/problem_list.html', context)

@login_required
def problem_detail(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    # Ограничение доступа
    if not request.user.is_staff and problem.author != request.user:
        return redirect('issues:problem_list')

    # Флаг, может ли пользователь оценить
    can_rate = (
        problem.author == request.user
        and problem.rating is None
        and problem.status in ['resolved', 'closed']
    )

    if request.method == 'POST' and 'rating_submit' in request.POST:
        print("[DEBUG] Получен POST-запрос на оценку")
        print("[DEBUG] Данные POST:", request.POST)

        rating_str = request.POST.get('rating')
        review = request.POST.get('review_text', '').strip()

        if rating_str and can_rate:
            try:
                rating = int(rating_str)
                if 1 <= rating <= 5:
                    # Обновляем объект из базы (на всякий случай)
                    problem.refresh_from_db()

                    # Проверяем ещё раз (на случай параллельных запросов)
                    if problem.rating is None:
                        problem.rating = rating
                        problem.review_text = review
                        problem.rated_at = timezone.now()
                        problem.rated_by = request.user
                        problem.save()

                        messages.success(request, f"Спасибо! Вы поставили оценку {rating} ★")

                        # Редирект на эту же страницу
                        return redirect('issues:problem_detail', pk=pk)

                        print(f"[DEBUG] Успешно сохранено: rating={problem.rating}, review='{problem.review_text}'")
                        messages.success(request, f"Спасибо! Вы поставили оценку {rating} ★")
                    else:
                        print("[DEBUG] Оценка уже была")
                        messages.warning(request, "Вы уже оценили эту заявку")
                else:
                    messages.error(request, "Оценка должна быть от 1 до 5")
            except ValueError:
                messages.error(request, "Неверный формат оценки")
        else:
            messages.error(request, "Ошибка: оценка не указана или недостаточно прав")
    else:
        print("[DEBUG] Запрос не POST или нет rating_submit")

    # Обновляем объект для шаблона
    problem.refresh_from_db()

    staff_list = User.objects.filter(is_staff=True).order_by('username')

    context = {
        'problem': problem,
        'can_rate': can_rate,
        'staff_list': staff_list,
    }

    return render(request, 'issues/problem_detail.html', context)

# Смена статуса (только staff)
@staff_member_required
def change_problem_status(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status and new_status != problem.status:
            # Сохраняем историю
            StatusHistory.objects.create(
                problem=problem,
                old_status=problem.status,
                new_status=new_status,
                changed_by=request.user
            )
            # Меняем статус
            problem.status = new_status

            if new_status in ['resolved', 'closed']:
                problem.resolved_by = request.user

            problem.save()

            if problem.author.email:
                send_status_change_email(problem, new_status)

            if problem.author != request.user:  # не уведомляем самого себя
                print(f"[NOTIF] Создаём уведомление для {problem.author.username}")
                Notification.objects.create(
                    user=problem.author,
                    message=f"Ваша заявка «{problem.title}» изменила статус на «{new_status}»",
                    problem=problem
                )
                print("[NOTIF] Уведомление создано")

    return redirect('issues:problem_detail', pk=pk)
@login_required
def problem_create(request):
    if request.method == 'POST':
        form = ProblemForm(request.POST, request.FILES)
        if form.is_valid():
            problem = form.save(commit=False)
            problem.author = request.user
            problem.save()
            send_new_problem_email(problem)

            if problem.assigned_to:
                Notification.objects.create(
                    user=problem.assigned_to,
                    message=_(f"Вам назначена новая заявка: {problem.title}"),
                    problem=problem
                )

            messages.success(request, _("Заявка создана!"))
            return redirect('issues:problem_list')
    else:
        form = ProblemForm()

    return render(request, 'issues/problem_create.html', {'form': form})

@user_passes_test(lambda u: u.is_superuser)
def delete_problem(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    if problem.status != 'closed':
        return redirect('issues:problem_detail', pk=pk)

    if request.method == 'POST':
        problem.delete()
        return redirect('issues:problem_list')

    return redirect('issues:problem_detail', pk=pk)

def home(request):
    # Можно передать что-то в шаблон, если нужно (например, статистику)
    context = {
        'total_problems': Problem.objects.count(),           # общее кол-во заявок
        'solved_problems': Problem.objects.filter(status='resolved').count(),
        'user': request.user if request.user.is_authenticated else None,
    }
    return render(request, 'issues/home.html', context)

def register(request):
    print("Метод запроса:", request.method)           # ← добавь
    print("POST данные:", request.POST)               # ← добавь

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        print("Форма валидна?", form.is_valid())      # ← ключевой print
        if form.is_valid():
            user = form.save()
            print("Создан пользователь:", user.username)
            login(request, user)
            messages.success(request, 'Регистрация успешна! Добро пожаловать!')
            return redirect('issues:problem_list')    # ← используй namespace
        else:
            print("Ошибки формы:", form.errors)       # ← покажет, что не так
    else:
        form = RegisterForm()

    return render(request, 'issues/register.html', {'form': form})

@staff_member_required
def statistics(request):
    # Существующая статистика по персоналу
    staff_stats = User.objects.filter(is_staff=True).annotate(
        total_participated=Count(
            'statushistory',  # related_name от StatusHistory к User (changed_by)
            distinct=True
        ),
        resolved_count=Count(
            'resolved_problems',
            filter=Q(resolved_problems__status__in=['resolved', 'closed']),
            distinct=True
        ),
        avg_rating=Avg(
            'resolved_problems__rating',
            filter=Q(resolved_problems__status__in=['resolved', 'closed'])
        ),
        rated_count=Count(
            'resolved_problems__rating',
            filter=Q(resolved_problems__status__in=['resolved', 'closed']) &
                   Q(resolved_problems__rating__isnull=False)
        )
    ).annotate(
        # Процент решённых
        resolved_percent=Case(
            When(total_participated=0, then=Value(0.0)),
            default=ExpressionWrapper(
                (F('resolved_count') * 100.0 / F('total_participated')),
                output_field=FloatField()
            )
        )
    ).order_by('-avg_rating', '-resolved_count')

    category_stats = Category.objects.annotate(
        total_problems=Count('problems'),
        resolved_problems=Count(
            'problems',
            filter=Q(problems__status__in=['resolved', 'closed'])
        ),
        avg_rating=Avg(
            'problems__rating',
            filter=Q(problems__status__in=['resolved', 'closed'])
        )
    ).order_by('-total_problems')

    for cat in category_stats:
        if cat.total_problems > 0:
            cat.resolved_percent = round((cat.resolved_problems / cat.total_problems) * 100, 1)
        else:
            cat.resolved_percent = 0

    context = {
        'staff_stats': staff_stats,
        'category_stats': category_stats,
        'total_problems_all': Problem.objects.count(),  # для %
    }

    return render(request, 'issues/statistics.html', context)

@staff_member_required
def assign_staff(request, pk):
    problem = get_object_or_404(Problem, pk=pk)
    if request.method == 'POST':
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            assigned_to = User.objects.get(id=assigned_to_id)
            problem.assigned_to = assigned_to
            problem.assigned_at = timezone.now()
            problem.save()
            # Уведомляем нового ответственного
            Notification.objects.create(
                user=assigned_to,
                message=_(f"Вам назначена заявка: {problem.title}"),
                problem=problem
            )
            messages.success(request, _("Ответственный назначен!"))
        else:
            problem.assigned_to = None
            problem.assigned_at = None
            problem.save()
            messages.success(request, _("Ответственный снят"))
    return redirect('issues:problem_detail', pk=pk)

@login_required
def take_task(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    # Проверяем, что заявка ещё не назначена и пользователь — сотрудник
    if problem.assigned_to:
        messages.warning(request, _("Заявка уже назначена другому сотруднику."))
    elif not request.user.is_staff:
        messages.error(request, _("Только сотрудники могут брать заявки в работу."))
    else:
        problem.assigned_to = request.user
        problem.assigned_at = timezone.now()
        problem.save()

        # Создаём уведомление (опционально)
        Notification.objects.create(
            user=request.user,
            message=_(f"Вы взяли в работу заявку: {problem.title}"),
            problem=problem
        )

        messages.success(request, _(f"Вы успешно взяли заявку «{problem.title}» в работу!"))

    return redirect('issues:problem_detail', pk=pk)