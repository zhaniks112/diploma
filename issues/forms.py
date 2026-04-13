from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import Problem, Category

class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['title', 'description', 'category', 'image', 'assigned_to']  # добавили category

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = True
        self.fields['category'].queryset = Category.objects.all().order_by('order', 'name')
        self.fields['category'].empty_label = _("Выберите категорию...")
        self.fields['category'].label = _("Категория проблемы (обязательно)")
        self.fields['assigned_to'].queryset = User.objects.filter(is_staff=True)
        self.fields['assigned_to'].required = False  # можно оставить пустым
        self.fields['assigned_to'].label = _("Назначить ответственного (опционально)")

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

class ProblemRatingForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['rating', 'review_text']   # ← обязательно должны быть оба поля!
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, str(i)) for i in range(1, 6)]),
            'review_text': forms.Textarea(attrs={'rows': 3}),
        }