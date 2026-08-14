from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from .models import (
    PersonalHealthProfile,
    WorkoutPlan,
    DietPlan,
    DailyLog,
    WorkoutLog,
    MealLog,
    Alert,
    AIChatMessage,
)
from .serializers import (
    PersonalHealthProfileSerializer,
    WorkoutPlanSerializer,
    DietPlanSerializer,
    DailyLogSerializer,
    WorkoutLogSerializer,
    MealLogSerializer,
    AlertSerializer,
    AIChatMessageSerializer,
)
from .services import (
    evaluate_health_signals,
    recompute_daily_nutrition_from_meals,
    generate_and_save_progress_insight,
)

User = get_user_model()

# --- 1. ONBOARDING HEALTH PROFILE ---
class PersonalHealthProfileView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PersonalHealthProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        try:
            return PersonalHealthProfile.objects.get(user=self.request.user)
        except PersonalHealthProfile.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        profile = self.get_object()
        if profile is None:
            return Response(
                {"detail": "Profile not created yet. Please complete onboarding."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        profile = self.get_object()
        if profile is not None:
            return Response({"detail": "Profile already exists. Use PUT or PATCH to update."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# --- 2. ACTIVE PLANS ---
class ActiveWorkoutPlanView(generics.RetrieveAPIView):
    serializer_class = WorkoutPlanSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        try:
            return WorkoutPlan.objects.get(user=self.request.user, is_active=True)
        except WorkoutPlan.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan is None:
            return Response({}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(plan)
        return Response(serializer.data)


class ActiveDietPlanView(generics.RetrieveAPIView):
    serializer_class = DietPlanSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        try:
            return DietPlan.objects.get(user=self.request.user, is_active=True)
        except DietPlan.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan is None:
            return Response({}, status=status.HTTP_200_OK)
        serializer = self.get_serializer(plan)
        return Response(serializer.data)


# --- 3. DAILY LOGGING, WORKOUT LOGGING & MEAL LOGGING ---
class DailyLogListCreateView(generics.ListCreateAPIView):
    serializer_class = DailyLogSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return DailyLog.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        date_val = request.data.get('date')
        if not date_val:
            return Response({"detail": "Date field is required."}, status=status.HTTP_400_BAD_REQUEST)

        existing_log = DailyLog.objects.filter(user=request.user, date=date_val).first()
        if existing_log:
            serializer = self.get_serializer(existing_log, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            evaluate_health_signals(request.user)
            generate_and_save_progress_insight(request.user, date_val)
            serializer.instance.refresh_from_db()
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        evaluate_health_signals(request.user)
        generate_and_save_progress_insight(request.user, date_val)
        serializer.instance.refresh_from_db()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkoutLogListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkoutLogSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return WorkoutLog.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        session_id = request.data.get('workout_session')
        date_val = request.data.get('date')
        if not session_id or not date_val:
            return Response({"detail": "workout_session and date are required fields."}, status=status.HTTP_400_BAD_REQUEST)

        existing_log = WorkoutLog.objects.filter(user=request.user, workout_session_id=session_id, date=date_val).first()
        if existing_log:
            serializer = self.get_serializer(existing_log, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            generate_and_save_progress_insight(request.user, date_val)
            return Response(serializer.data, status=status.HTTP_200_OK)

        response = super().create(request, *args, **kwargs)
        generate_and_save_progress_insight(request.user, date_val)
        return response


class MealLogListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/fitness/logs/meal/?date=YYYY-MM-DD  — meals logged (all, or for one date)
    POST /api/fitness/logs/meal/  body: { meal, date, completed? }
        -> marks a meal eaten/un-eaten, recomputes that day's DailyLog
           calorie/protein/carb/fat totals, then regenerates the AI progress
           insight for that day.
    """
    serializer_class = MealLogSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        qs = MealLog.objects.filter(user=self.request.user)
        date_val = self.request.query_params.get('date')
        if date_val:
            qs = qs.filter(date=date_val)
        return qs

    def create(self, request, *args, **kwargs):
        meal_id = request.data.get('meal')
        date_val = request.data.get('date')
        if not meal_id or not date_val:
            return Response({"detail": "meal and date are required fields."}, status=status.HTTP_400_BAD_REQUEST)

        completed = request.data.get('completed', True)

        existing_log = MealLog.objects.filter(user=request.user, meal_id=meal_id, date=date_val).first()
        if existing_log:
            serializer = self.get_serializer(existing_log, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        updated_daily_log = recompute_daily_nutrition_from_meals(request.user, date_val)
        insight_text = generate_and_save_progress_insight(request.user, date_val)

        return Response({
            "meal_log": serializer.data,
            "daily_totals": {
                "calories_consumed": updated_daily_log.calories_consumed if updated_daily_log else None,
                "protein_consumed": updated_daily_log.protein_consumed if updated_daily_log else None,
                "carbs_consumed": updated_daily_log.carbs_consumed if updated_daily_log else None,
                "fats_consumed": updated_daily_log.fats_consumed if updated_daily_log else None,
            } if completed else None,
            "ai_insight": insight_text,
        }, status=status.HTTP_200_OK if existing_log else status.HTTP_201_CREATED)


# --- 4. SYSTEM ALERTS LIST & RESOLUTION ---
class AlertListView(generics.ListAPIView):
    serializer_class = AlertSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user)


class AlertResolveView(generics.UpdateAPIView):
    serializer_class = AlertSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Alert.objects.all()

    def get_queryset(self):
        return Alert.objects.filter(user=self.request.user, status='active')

    def update(self, request, *args, **kwargs):
        alert = self.get_object()
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()
        return Response({
            "message": "Alert marked as resolved successfully.",
            "alert": self.get_serializer(alert).data
        }, status=status.HTTP_200_OK)


# --- 5. DASHBOARD PROGRESS STATS & CHART AGGREGATOR ---
class DashboardSummaryView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user

        logs = list(DailyLog.objects.filter(user=user).order_by('date')[:30])

        weight_history = []
        calorie_history = []
        water_history = []
        fatigue_history = []

        for log in logs:
            if log.weight_logged is not None:
                weight_history.append({"date": str(log.date), "weight": log.weight_logged})
            if log.calories_consumed is not None:
                calorie_history.append({"date": str(log.date), "calories": log.calories_consumed})
            water_history.append({"date": str(log.date), "water": log.water_intake})
            if log.fatigue_level is not None:
                fatigue_history.append({"date": str(log.date), "fatigue": log.fatigue_level})

        total_workouts = WorkoutLog.objects.filter(user=user).count()
        completed_workouts = WorkoutLog.objects.filter(user=user, completed=True).count()
        completion_rate = round((completed_workouts / total_workouts * 100), 2) if total_workouts > 0 else 0.0

        active_alerts = Alert.objects.filter(user=user, status='active').values('id', 'type', 'message')

        active_diet = DietPlan.objects.filter(user=user, is_active=True).first()
        active_workout = WorkoutPlan.objects.filter(user=user, is_active=True).first()

        profile = PersonalHealthProfile.objects.filter(user=user).first()
        today_log = DailyLog.objects.filter(user=user, date=timezone.now().date()).first()

        return Response({
            "weight_history": weight_history,
            "calorie_history": calorie_history,
            "water_history": water_history,
            "fatigue_history": fatigue_history,
            "workout_stats": {
                "total_logged": total_workouts,
                "completed": completed_workouts,
                "completion_rate": completion_rate
            },
            "active_alerts": list(active_alerts),
            "targets": {
                "calories": active_diet.target_calories if active_diet else None,
                "protein": active_diet.target_protein if active_diet else None,
                "carbs": active_diet.target_carbs if active_diet else None,
                "fats": active_diet.target_fats if active_diet else None,
                "workout_title": active_workout.title if active_workout else None,
                "water_ml": round(profile.weight * 35) if profile else None,
            },
            "today_water_ml": today_log.water_intake if today_log else 0,
            "today_insight": today_log.ai_insight if today_log else None,
        }, status=status.HTTP_200_OK)


# --- 6. AI TRAINER CHAT HISTORY ---
class AIChatHistoryView(generics.ListAPIView):
    serializer_class = AIChatMessageSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return AIChatMessage.objects.filter(user=self.request.user)
