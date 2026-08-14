from django.urls import path
from .views import (
    PersonalHealthProfileView,
    ActiveWorkoutPlanView,
    ActiveDietPlanView,
    DailyLogListCreateView,
    WorkoutLogListCreateView,
    MealLogListCreateView,
    AlertListView,
    AlertResolveView,
    DashboardSummaryView,
    AIChatHistoryView,
)

urlpatterns = [
    # Onboarding & Active Plans
    path('profile/', PersonalHealthProfileView.as_view(), name='fitness_profile'),
    path('plans/workout/', ActiveWorkoutPlanView.as_view(), name='active_workout_plan'),
    path('plans/diet/', ActiveDietPlanView.as_view(), name='active_diet_plan'),

    # Chronological Daily, Workout & Meal Tracking Logs
    path('logs/daily/', DailyLogListCreateView.as_view(), name='daily_log_list_create'),
    path('logs/workout/', WorkoutLogListCreateView.as_view(), name='workout_log_list_create'),
    path('logs/meal/', MealLogListCreateView.as_view(), name='meal_log_list_create'),

    # Burnout, Plateau & Hydration Detection Alerts
    path('alerts/', AlertListView.as_view(), name='alert_list'),
    path('alerts/<int:pk>/resolve/', AlertResolveView.as_view(), name='alert_resolve'),

    # Visual Progress Charts Dashboard Stats
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),

    # AI Trainer live chat — persisted history (used to seed the WebSocket connection)
    path('ai-chat/history/', AIChatHistoryView.as_view(), name='ai_chat_history'),
]
