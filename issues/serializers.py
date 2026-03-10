from rest_framework import serializers
from .models import Category, Problem, StatusHistory
from django.contrib.auth import get_user_model

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

class ProblemSerializer(serializers.ModelSerializer):
    author = serializers.ReadOnlyField(source='author.username')
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source='category', queryset=Category.objects.all(), write_only=True, required=False)

    class Meta:
        model = Problem
        fields = ['id', 'title', 'description', 'category', 'category_id', 'status', 'image', 'author', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']

class StatusHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.ReadOnlyField(source='changed_by.username')

    class Meta:
        model = StatusHistory
        fields = ['id', 'problem', 'old_status', 'new_status', 'changed_at', 'changed_by']
