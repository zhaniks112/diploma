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
import json
from .utils import send_new_problem_email, send_status_change_email
from django.utils.translation import gettext_lazy as _
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


@login_required
def problem_list(request):
    problems = Problem.objects.all()

    if request.user.is_superuser:
        pass  # суперпользователь видит все заявки
    elif request.user.is_staff:
        has_profile = hasattr(request.user, 'staff_profile')
        if has_profile:
            staff_categories = request.user.staff_profile.categories.all()
        else:
            staff_categories = Category.objects.none()

        problems = problems.filter(category__in=staff_categories)
    else:
        problems = problems.filter(author=request.user)

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

    problem.refresh_from_db()

    if problem.category:
        staff_list = User.objects.filter(
            is_staff=True,
            staff_profile__categories=problem.category
        ).order_by('username')
    else:
        staff_list = User.objects.filter(is_staff=True).order_by('username')

    can_take = False
    category_warning = False

    if request.user.is_staff and not problem.assigned_to:
        has_profile = hasattr(request.user, 'staff_profile')
        if problem.category and has_profile:
            can_take = request.user.staff_profile.categories.filter(
                id=problem.category.id
            ).exists()
            category_warning = not can_take
        else:
            can_take = True
    context = {
        'problem': problem,
        'can_rate': can_rate,
        'staff_list': staff_list,
        'can_take': can_take,
        'category_warning': category_warning,
    }

    return render(request, 'issues/problem_detail.html', context)

# Смена статуса (только staff)
@staff_member_required
def change_problem_status(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status and new_status != problem.status:
            StatusHistory.objects.create(
                problem=problem,
                old_status=problem.status,
                new_status=new_status,
                changed_by=request.user
            )
            problem.status = new_status

            if new_status in ['resolved', 'closed']:
                problem.resolved_by = request.user

            problem.save()

            if problem.author.email:
                send_status_change_email(problem, new_status)

            if problem.author != request.user:
                Notification.objects.create(
                    user=problem.author,
                    message_key="notification.status_changed",
                    message_params={"title": problem.title, "status": new_status},  # ← сырой статус
                    problem=problem
                )

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
    return redirect('account_signup')  # перенаправляет на страницу allauth

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

    category_stats = list(Category.objects.annotate(
        total_problems=Count('problems'),
        resolved_problems=Count(
            'problems',
            filter=Q(problems__status__in=['resolved', 'closed'])
        ),
        avg_rating=Avg(
            'problems__rating',
            filter=Q(problems__status__in=['resolved', 'closed'])
        )
    ).filter(total_problems__gt=0)
    .order_by('-total_problems'))  # ← list() здесь

    for cat in category_stats:
        if cat.total_problems > 0:
            cat.resolved_percent = round((cat.resolved_problems / cat.total_problems) * 100, 1)
        else:
            cat.resolved_percent = 0

    print("DEBUG category_stats count:", len(category_stats))  # ← добавь
    print("DEBUG chart_labels:", [cat.name for cat in category_stats])  # ← добавь

    context = {
        'staff_stats': staff_stats,
        'category_stats': category_stats,
        'total_problems_all': Problem.objects.count(),
        'chart_labels': [cat.name for cat in category_stats],  # теперь работает
        'chart_total': [cat.total_problems for cat in category_stats],
        'chart_resolved': [cat.resolved_problems for cat in category_stats],
    }

    return render(request, 'issues/statistics.html', context)

@staff_member_required
def assign_staff(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    if request.method == 'POST':
        assigned_to_id = request.POST.get('assigned_to')
        if assigned_to_id:
            assigned_to = User.objects.get(id=assigned_to_id)

            # Проверка — сотрудник подходит по категории?
            if problem.category and not assigned_to.staff_profile.categories.filter(
                id=problem.category.id
            ).exists():
                messages.error(request, _("Этот сотрудник не обслуживает данную категорию."))
                return redirect('issues:problem_detail', pk=pk)

            problem.assigned_to = assigned_to
            problem.assigned_at = timezone.now()
            problem.save()

            Notification.objects.create(
                user=assigned_to,
                message_key="notification.assigned",
                message_params={"title": problem.title},
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

    if problem.assigned_to:
        messages.warning(request, _("Заявка уже назначена другому сотруднику."))
    elif not request.user.is_staff:
        messages.error(request, _("Только сотрудники могут брать заявки в работу."))
    else:
        # Проверка по категории
        has_profile = hasattr(request.user, 'staff_profile')
        category_match = (
            not problem.category or  # если у заявки нет категории — разрешаем
            (has_profile and request.user.staff_profile.categories.filter(
                id=problem.category.id
            ).exists())
        )

        if not category_match:
            messages.error(request, _("Вы не можете взять эту заявку — она не входит в ваши категории."))
        else:
            problem.assigned_to = request.user
            problem.assigned_at = timezone.now()
            problem.save()

            Notification.objects.create(
                user=request.user,
                message_key="notification.taken_to_work",
                message_params={"title": problem.title},
                problem=problem
            )
            messages.success(
                request,
                _("Вы успешно взяли заявку «%(title)s» в работу!") % {"title": problem.title}
            )

    return redirect('issues:problem_detail', pk=pk)

@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()

    # Редирект на заявку если есть, иначе на список
    if notification.problem:
        return redirect('issues:problem_detail', pk=notification.problem.pk)
    return redirect('issues:problem_list')

@login_required
def reassign_task(request, pk):
    problem = get_object_or_404(Problem, pk=pk)

    if problem.status in ['resolved', 'closed']:
        messages.error(request, _("Нельзя передать завершённую заявку."))
        return redirect('issues:problem_detail', pk=pk)

    # Только текущий ответственный может переназначить
    if problem.assigned_to != request.user:
        messages.error(request, _("Вы не являетесь ответственным за эту заявку."))
        return redirect('issues:problem_detail', pk=pk)

    if request.method == 'POST':
        new_assigned_id = request.POST.get('new_assigned_to')
        if new_assigned_id:
            new_assigned = get_object_or_404(User, id=new_assigned_id)

            # Проверка — новый сотрудник той же категории
            if problem.category and not new_assigned.staff_profile.categories.filter(
                    id=problem.category.id
            ).exists():
                messages.error(request, _("Этот сотрудник не обслуживает данную категорию."))
                return redirect('issues:problem_detail', pk=pk)

            old_assigned = problem.assigned_to
            problem.assigned_to = new_assigned
            problem.assigned_at = timezone.now()
            problem.save()

            # Уведомление новому сотруднику
            Notification.objects.create(
                user=new_assigned,
                message_key="notification.assigned",
                message_params={"title": problem.title},
                problem=problem
            )

            # Уведомление старому сотруднику
            Notification.objects.create(
                user=old_assigned,
                message_key="notification.reassigned_from",
                message_params={"title": problem.title, "to": new_assigned.username},
                problem=problem
            )

            messages.success(request, _("Заявка передана сотруднику %(username)s.") % {
                "username": new_assigned.username
            })

    return redirect('issues:problem_detail', pk=pk)

class ProblemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Problem
    fields = ['title', 'description', 'category', 'image'] # Поля, которые можно менять
    template_name = 'issues/problem_create.html' # Используем тот же красивый шаблон, что и для создания

    def test_func(self):
        """Проверка: редактировать может только автор или персонал"""
        problem = self.get_object()
        return self.request.user == problem.author or self.request.user.is_staff