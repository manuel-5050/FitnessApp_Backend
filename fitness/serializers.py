from rest_framework import serializers
from django.contrib.auth import get_user_model
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
from .services import generate_and_save_fitness_plans, daily_water_target_ml

User = get_user_model()

# --- 1. PERSONAL HEALTH PROFILE ---
class PersonalHealthProfileSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    bmi = serializers.FloatField(read_only=True)
    daily_water_target_ml = serializers.SerializerMethodField()

    class Meta:
        model = PersonalHealthProfile
        fields = (
            'id', 'user', 'gender', 'age', 'height', 'weight', 'activity_level',
            'fitness_goal', 'dietary_restrictions', 'medical_conditions', 'bmi',
            'daily_water_target_ml',
        )

    def get_daily_water_target_ml(self, profile):
        return daily_water_target_ml(profile)

    def create(self, validated_data):
        profile = super().create(validated_data)
        # Automatic trigger: Runs our AI Bridge immediately upon onboarding profile completion!
        generate_and_save_fitness_plans(profile)
        return profile


# --- 2. NESTED PLAN SERIALIZERS (To cleanly structure the JSON outputs) ---

class ExerciseSerializer(serializers.ModelSerializer):
    custom_gif_url = serializers.URLField(required=False, allow_null=True)

    class Meta:
        model = Exercise
        fields = ('id', 'name', 'custom_gif_url', 'sets', 'reps', 'rest_time', 'order')


class WorkoutSessionSerializer(serializers.ModelSerializer):
    exercises = ExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = WorkoutSession
        fields = ('id', 'day_of_week', 'session_name', 'notes', 'exercises')


class WorkoutPlanSerializer(serializers.ModelSerializer):
    sessions = WorkoutSessionSerializer(many=True, read_only=True)

    class Meta:
        model = WorkoutPlan
        fields = ('id', 'title', 'target_goal', 'start_date', 'end_date', 'is_active', 'is_ai_generated', 'sessions', 'created_at')


class MealSerializer(serializers.ModelSerializer):
    custom_image_url = serializers.URLField(required=False, allow_null=True)

    class Meta:
        model = Meal
        fields = ('id', 'meal_time', 'name', 'custom_image_url', 'food_items', 'calories', 'protein', 'carbs', 'fats')


class DietPlanSerializer(serializers.ModelSerializer):
    meals = MealSerializer(many=True, read_only=True)

    class Meta:
        model = DietPlan
        fields = ('id', 'title', 'start_date', 'end_date', 'is_active', 'is_ai_generated', 'target_calories', 'target_protein', 'target_carbs', 'target_fats', 'meals', 'created_at')


# --- 3. CHRONOLOGICAL LOGGING SERIALIZERS ---

class DailyLogSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = DailyLog
        fields = (
            'id', 'user', 'date', 'weight_logged', 'water_intake',
            'calories_consumed', 'protein_consumed', 'carbs_consumed', 'fats_consumed',
            'fatigue_level', 'notes',
        )
        # The macro fields are normally written by recompute_daily_nutrition_from_meals
        # (see fitness/services.py) when meals get marked eaten, but the API still
        # accepts them directly for manual-entry days.


class WorkoutLogSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = WorkoutLog
        fields = ('id', 'user', 'workout_session', 'date', 'completed', 'duration_minutes')


class MealLogSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    meal_name = serializers.CharField(source='meal.name', read_only=True)
    meal_time = serializers.CharField(source='meal.meal_time', read_only=True)

    class Meta:
        model = MealLog
        fields = ('id', 'user', 'meal', 'meal_name', 'meal_time', 'date', 'completed', 'created_at')


# --- 4. SYSTEM ALERTS SERIALIZERS ---

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ('id', 'type', 'status', 'message', 'created_at', 'resolved_at')
        read_only_fields = ('id', 'type', 'status', 'message', 'created_at', 'resolved_at')


# --- 5. AI TRAINER CHAT SERIALIZER ---

class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ('id', 'role', 'text', 'created_at')
        read_only_fields = ('id', 'role', 'created_at')
