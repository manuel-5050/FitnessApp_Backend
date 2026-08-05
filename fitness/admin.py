from django.contrib import admin
from .models import PersonalHealthProfile, WorkoutPlan, WorkoutSession, Exercise, DietPlan, Meal, DailyLog, WorkoutLog, Alert, TrainerRelationship

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
    list_display = ['user', 'date', 'weight_logged', 'water_intake', 'calories_consumed', 'fatigue_level']
    list_filter = ['date']
    search_fields = ['user__email']

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'status', 'created_at']
    list_filter = ['type', 'status']
    search_fields = ['user__email']

@admin.register(TrainerRelationship)
class TrainerRelationshipAdmin(admin.ModelAdmin):
    list_display = ['trainer', 'client', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['trainer__email', 'client__email']

admin.site.register(WorkoutSession)
admin.site.register(Exercise)
admin.site.register(Meal)
admin.site.register(WorkoutLog)