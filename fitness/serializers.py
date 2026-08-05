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
    Alert,
    TrainerRelationship,
    TrainerProfile,
    Connection,
    Conversation,
    Message,
)
from .services import generate_and_save_fitness_plans

User = get_user_model()

# --- 1. PERSONAL HEALTH PROFILE ---
class PersonalHealthProfileSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    bmi = serializers.FloatField(read_only=True)

    class Meta:
        model = PersonalHealthProfile
        fields = ('id', 'user', 'gender', 'age', 'height', 'weight', 'activity_level', 'fitness_goal', 'dietary_restrictions', 'medical_conditions', 'bmi')

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
        fields = ('id', 'user', 'date', 'weight_logged', 'water_intake', 'calories_consumed', 'fatigue_level', 'notes')


class WorkoutLogSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = WorkoutLog
        fields = ('id', 'user', 'workout_session', 'date', 'completed', 'duration_minutes')


# --- 4. SYSTEM ALERTS SERIALIZERS ---

class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = ('id', 'type', 'status', 'message', 'created_at', 'resolved_at')
        read_only_fields = ('id', 'type', 'status', 'message', 'created_at', 'resolved_at')


# --- 5. TRAINER CLIENT ROSTER SERIALIZERS ---

class TrainerClientSerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    client_email = serializers.EmailField(source='client.email', read_only=True)
    client_first_name = serializers.CharField(source='client.first_name', read_only=True)
    client_last_name = serializers.CharField(source='client.last_name', read_only=True)
    profile = PersonalHealthProfileSerializer(source='client.profile', read_only=True)
    active_alerts = serializers.SerializerMethodField()

    class Meta:
        model = TrainerRelationship
        fields = ('id', 'client_id', 'client_email', 'client_first_name', 'client_last_name', 'profile', 'active_alerts', 'is_active')

    # Aggregates active burnout & plateau warnings for the trainer's roster
    def get_active_alerts(self, obj):
        alerts = Alert.objects.filter(user=obj.client, status='active')
        return AlertSerializer(alerts, many=True).data


# --- 6. TRAINER DISCOVERY, CONNECTIONS, MESSAGING ---

def _full_name(user):
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


class TrainerProfileSerializer(serializers.ModelSerializer):
    """Used both for a trainer writing their own profile (onboarding) and
    for read-only display via TrainerListSerializer/TrainerDetailSerializer."""
    class Meta:
        model = TrainerProfile
        fields = ('id', 'bio', 'specialties', 'years_experience', 'certifications', 'rating')
        read_only_fields = ('id', 'rating')


class TrainerListSerializer(serializers.Serializer):
    """Read-only shape for GET /api/fitness/trainers/ — one row per trainer User."""
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    bio = serializers.CharField(source='trainer_profile.bio', default='')
    specialties = serializers.ListField(source='trainer_profile.specialties', default=list)
    years_experience = serializers.IntegerField(source='trainer_profile.years_experience', default=None)
    rating = serializers.FloatField(source='trainer_profile.rating', default=0.0)
    client_count = serializers.SerializerMethodField()

    def get_name(self, user):
        return _full_name(user)

    def get_client_count(self, user):
        return TrainerRelationship.objects.filter(trainer=user, is_active=True).count()


class TrainerDetailSerializer(TrainerListSerializer):
    """Adds fields only needed on the single-trainer profile page."""
    certifications = serializers.ListField(source='trainer_profile.certifications', default=list)
    connection_status = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()

    def get_connection_status(self, trainer_user):
        request_user = self.context['request'].user
        connection = (
            Connection.objects.filter(from_user=request_user, to_user=trainer_user)
            .order_by('-created_at')
            .first()
            or Connection.objects.filter(from_user=trainer_user, to_user=request_user)
            .order_by('-created_at')
            .first()
        )
        if not connection:
            return 'none'
        return connection.status if connection.status != 'declined' else 'none'

    def get_conversation_id(self, trainer_user):
        request_user = self.context['request'].user
        conversation = Conversation.objects.filter(trainer=trainer_user, client=request_user).first()
        return conversation.id if conversation else None


class ClientListSerializer(serializers.Serializer):
    """Read-only shape for GET /api/fitness/clients/ — trainers browsing prospects."""
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    fitness_goal = serializers.CharField(source='profile.fitness_goal', default=None)
    activity_level = serializers.CharField(source='profile.activity_level', default=None)
    has_active_alert = serializers.SerializerMethodField()

    def get_name(self, user):
        return _full_name(user)

    def get_has_active_alert(self, user):
        return Alert.objects.filter(user=user, status='active').exists()


class ConnectionSerializer(serializers.Serializer):
    """Read-only shape for GET /api/fitness/connections/."""
    id = serializers.IntegerField()
    direction = serializers.SerializerMethodField()
    status = serializers.CharField()
    counterpart_id = serializers.SerializerMethodField()
    counterpart_name = serializers.SerializerMethodField()
    counterpart_role = serializers.SerializerMethodField()
    note = serializers.CharField()
    created_at = serializers.DateTimeField()
    conversation_id = serializers.SerializerMethodField()

    def _counterpart(self, connection):
        request_user = self.context['request'].user
        return connection.to_user if connection.from_user_id == request_user.id else connection.from_user

    def get_direction(self, connection):
        request_user = self.context['request'].user
        return 'outgoing' if connection.from_user_id == request_user.id else 'incoming'

    def get_counterpart_id(self, connection):
        return self._counterpart(connection).id

    def get_counterpart_name(self, connection):
        return _full_name(self._counterpart(connection))

    def get_counterpart_role(self, connection):
        return self._counterpart(connection).role

    def get_conversation_id(self, connection):
        conversation = Conversation.objects.filter(connection=connection).first()
        return conversation.id if conversation else None


class ConversationListSerializer(serializers.Serializer):
    """Read-only shape for GET /api/fitness/conversations/."""
    id = serializers.IntegerField()
    counterpart_id = serializers.SerializerMethodField()
    counterpart_name = serializers.SerializerMethodField()
    counterpart_role = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    def _counterpart(self, conversation):
        request_user = self.context['request'].user
        return conversation.client if conversation.trainer_id == request_user.id else conversation.trainer

    def get_counterpart_id(self, conversation):
        return self._counterpart(conversation).id

    def get_counterpart_name(self, conversation):
        return _full_name(self._counterpart(conversation))

    def get_counterpart_role(self, conversation):
        return self._counterpart(conversation).role

    def get_last_message(self, conversation):
        last = conversation.messages.order_by('-created_at').first()
        return last.text if last else None

    def get_last_message_at(self, conversation):
        last = conversation.messages.order_by('-created_at').first()
        return last.created_at if last else None


class MessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'conversation', 'sender', 'sender_id', 'text', 'created_at')
        read_only_fields = ('id', 'sender', 'sender_id', 'created_at')


