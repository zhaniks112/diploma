from django.contrib import admin
from .models import Category, Problem, StatusHistory

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order', 'problems_count')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

    def problems_count(self, obj):
        return obj.problems.count()

    problems_count.short_description = "Заявок"

@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'status', 'author', 'created_at')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'description', 'author__username')

@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'problem', 'old_status', 'new_status', 'changed_at', 'changed_by')
