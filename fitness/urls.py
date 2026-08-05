from django.urls import path
from .views import (
    PersonalHealthProfileView,
    ActiveWorkoutPlanView,
    ActiveDietPlanView,
    DailyLogListCreateView,
    WorkoutLogListCreateView,
    AlertListView,
    AlertResolveView,
    TrainerClientListView,
    TrainerOverrideDietPlanView,
    DashboardSummaryView,
    TrainerListView,
    TrainerDetailView,
    ClientListView,
    TrainerProfileView,
    ConnectionRequestView,
    ConnectionListView,
    ConnectionAcceptView,
    ConnectionDeclineView,
    ConversationListView,
    ConversationMessagesView,
)

urlpatterns = [
    # Onboarding & Active Plans
    path('profile/', PersonalHealthProfileView.as_view(), name='fitness_profile'),
    path('plans/workout/', ActiveWorkoutPlanView.as_view(), name='active_workout_plan'),
    path('plans/diet/', ActiveDietPlanView.as_view(), name='active_diet_plan'),
    
    # Chronological Daily & Workout Tracking Logs (Step 7)
    path('logs/daily/', DailyLogListCreateView.as_view(), name='daily_log_list_create'),
    path('logs/workout/', WorkoutLogListCreateView.as_view(), name='workout_log_list_create'),
    
    # Burnout & Plateau Detection Alerts (Step 8)
    path('alerts/', AlertListView.as_view(), name='alert_list'),
    path('alerts/<int:pk>/resolve/', AlertResolveView.as_view(), name='alert_resolve'),
    
    # Trainer Roster & Plan Overrides
    path('trainer-clients/', TrainerClientListView.as_view(), name='trainer_client_list'), # <--- Change to hyphen!
    path('trainer/override-diet/', TrainerOverrideDietPlanView.as_view(), name='trainer_override_diet'),
    
    # Visual Progress Charts Dashboard Stats (Step 9)
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),

    # Trainer discovery (client browsing) & the trainer's own public profile
    path('trainers/', TrainerListView.as_view(), name='trainer_list'),
    path('trainers/<int:pk>/', TrainerDetailView.as_view(), name='trainer_detail'),
    path('trainer-profile/', TrainerProfileView.as_view(), name='trainer_profile'),

    # Client discovery (trainer browsing)
    path('clients/', ClientListView.as_view(), name='client_list'),

    # Connection requests (browse -> request -> accept/decline)
    path('connections/', ConnectionListView.as_view(), name='connection_list'),
    path('connections/request/', ConnectionRequestView.as_view(), name='connection_request'),
    path('connections/<int:pk>/accept/', ConnectionAcceptView.as_view(), name='connection_accept'),
    path('connections/<int:pk>/decline/', ConnectionDeclineView.as_view(), name='connection_decline'),

    # Conversations & messages (REST history; live delivery is via Channels)
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<int:pk>/messages/', ConversationMessagesView.as_view(), name='conversation_messages'),
]
