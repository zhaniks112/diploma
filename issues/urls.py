from django.urls import path
from rest_framework.urls import app_name

from . import views

app_name='issues'

urlpatterns = [
    path('', views.home, name='home'),
    path('create/', views.problem_create, name='problem_create'),
    path('problems/', views.problem_list, name='problem_list'),
    path('<int:pk>/', views.problem_detail, name='problem_detail'),
    path('<int:pk>/change-status/', views.change_problem_status, name='change_problem_status'),
    path('problem/<int:pk>/delete/', views.delete_problem, name='delete_problem'),
    path('register/', views.register, name='register'),
    path('statistics/', views.statistics, name='statistics'),
    path('problems/<int:pk>/assign/', views.assign_staff, name='assign_staff'),
    path('problems/<int:pk>/take/', views.take_task, name='take_task'),

    # path('<int:pk>/edit/', views.problem_update, name='problem_update'),
]