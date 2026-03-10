# issues/api_urls.py  ← новый файл
from django.urls import path
from uni_issues.issues import views

urlpatterns = [
    # здесь будут только API-вьюхи
    # path('problems/', views.ProblemListAPIView.as_view(), name='api-problem-list'),
    # path('problems/<int:pk>/', views.ProblemDetailAPIView.as_view(), name='api-problem-detail'),
    # и т.д.
]