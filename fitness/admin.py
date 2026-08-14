from django.contrib import admin
from .models import (
    PersonalHealthProfile,
    WorkoutPlan,
    WorkoutSession,
    Exercise,
    DietPlan,
    Meal,
    DailyLog,
    WorkoutLog,
    MealLog,
    Alert,
    AIChatMessage,
)

@admin.register(PersonalHealthProfile)
class PersonalHealthProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'age', 'height', 'weight', 'activity_level', 'fitness_goal']
    search_fields = ['user__email']

@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'target_goal', 'is_active', 'is_ai_generated', 'created_at']
    list_filter = ['is_active', 'is_ai_generated']
    search_fields = ['user__email']

@admin.register(DietPlan)
class DietPlanAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'target_calories', 'is_active', 'is_ai_generated', 'created_at']
    list_filter = ['is_active', 'is_ai_generated']
    search_fields = ['user__email']

@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'date', 'weight_logged', 'water_intake',
        'calories_consumed', 'protein_consumed', 'carbs_consumed', 'fats_consumed',
        'fatigue_level',
    ]
    list_filter = ['date']
    search_fields = ['user__email']

@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'meal', 'date', 'completed']
    list_filter = ['completed', 'date']
    search_fields = ['user__email', 'meal__name']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    # type now includes 'hydration' alongside 'burnout'/'plateau' — no code
    # change needed here since list_filter reads choices off the model.
    list_display = ['user', 'type', 'status', 'created_at']
    list_filter = ['type', 'status']
    search_fields = ['user__email']

@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'created_at']
    list_filter = ['role']
    search_fields = ['user__email', 'text']

admin.site.register(WorkoutSession)
admin.site.register(Exercise)
admin.site.register(Meal)
admin.site.register(WorkoutLog)
