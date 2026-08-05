from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    PersonalHealthProfile,
    WorkoutPlan,
    DietPlan,
    DailyLog,
    WorkoutLog,
    Alert,
    TrainerRelationship,
    TrainerProfile,
    Connection,
    Conversation,
    Message,
)
from .serializers import (
    PersonalHealthProfileSerializer,
    WorkoutPlanSerializer,
    DietPlanSerializer,
    DailyLogSerializer,
    WorkoutLogSerializer,
    AlertSerializer,
    TrainerClientSerializer,
    TrainerProfileSerializer,
    TrainerListSerializer,
    TrainerDetailSerializer,
    ClientListSerializer,
    ConnectionSerializer,
    ConversationListSerializer,
    MessageSerializer,
)
from .services import evaluate_burnout_and_plateau

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
            # CORRECTED: Return a 404 so React knows they haven't completed onboarding yet!
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


# --- 3. DAILY LOGGING & WORKOUT LOGGING ---
class DailyLogListCreateView(generics.ListCreateAPIView):
    serializer_class = DailyLogSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return DailyLog.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        date_val = request.data.get('date')
        if not date_val:
            return Response({"detail": "Date field is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # UPSERT behavior
        existing_log = DailyLog.objects.filter(user=request.user, date=date_val).first()
        if existing_log:
            serializer = self.get_serializer(existing_log, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            evaluate_burnout_and_plateau(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        evaluate_burnout_and_plateau(request.user)
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

        # UPSERT behavior
        existing_log = WorkoutLog.objects.filter(user=request.user, workout_session_id=session_id, date=date_val).first()
        if existing_log:
            serializer = self.get_serializer(existing_log, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return super().create(request, *args, **kwargs)


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


# --- 5. TRAINER ENDPOINTS (roster + plan override) ---
class TrainerClientListView(generics.ListAPIView):
    serializer_class = TrainerClientSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # Only allow 'TRAINER' or 'ADMIN' roles to access client lists
        if self.request.user.role not in ['TRAINER', 'ADMIN']:
            raise PermissionDenied("Only accounts with the Trainer role can access client rosters.")
        return TrainerRelationship.objects.filter(trainer=self.request.user, is_active=True)


class TrainerOverrideDietPlanView(generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        if request.user.role not in ['TRAINER', 'ADMIN']:
            raise PermissionDenied("Only trainers can override client plans.")
            
        client_id = request.data.get('client_id')
        target_calories = request.data.get('target_calories')
        target_protein = request.data.get('target_protein', 150)
        target_carbs = request.data.get('target_carbs', 200)
        target_fats = request.data.get('target_fats', 70)
        title = request.data.get('title', 'Trainer Assigned Custom Diet')
        
        if not client_id or not target_calories:
            return Response({"detail": "client_id and target_calories are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Ensure they are the assigned trainer
        relationship = TrainerRelationship.objects.filter(trainer=request.user, client_id=client_id, is_active=True).first()
        if not relationship and request.user.role != 'ADMIN':
            raise PermissionDenied("You are not assigned as the trainer for this client.")
            
        # Create plan (is_ai_generated = False)
        plan = DietPlan.objects.create(
            user_id=client_id,
            trainer=request.user,
            title=title,
            target_calories=target_calories,
            target_protein=target_protein,
            target_carbs=target_carbs,
            target_fats=target_fats,
            is_active=True,
            is_ai_generated=False
        )
        
        return Response({
            "message": "Client diet plan overridden successfully by trainer.",
            "plan_id": plan.id,
            "title": plan.title,
            "is_ai_generated": plan.is_ai_generated
        }, status=status.HTTP_201_CREATED)


# --- 6. DASHBOARD PROGRESS STATS & CHART AGGREGATOR ---
class DashboardSummaryView(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Fetch past 30 days of logs sorted ascending for line charts
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
                
        # Workout completion stats
        total_workouts = WorkoutLog.objects.filter(user=user).count()
        completed_workouts = WorkoutLog.objects.filter(user=user, completed=True).count()
        completion_rate = round((completed_workouts / total_workouts * 100), 2) if total_workouts > 0 else 0.0
        
        # Active alert flags
        active_alerts = Alert.objects.filter(user=user, status='active').values('id', 'type', 'message')
        
        # Currently active diet and workout goals
        active_diet = DietPlan.objects.filter(user=user, is_active=True).first()
        active_workout = WorkoutPlan.objects.filter(user=user, is_active=True).first()
        
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
                "workout_title": active_workout.title if active_workout else None
            }
        }, status=status.HTTP_200_OK)


# --- 7. TRAINER DISCOVERY (client browses trainers) ---
class TrainerListView(generics.ListAPIView):
    """GET /api/fitness/trainers/?search=<q>"""
    serializer_class = TrainerListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = User.objects.filter(role='TRAINER').select_related('trainer_profile')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(trainer_profile__specialties__icontains=search)
            )
        return queryset


class TrainerDetailView(generics.RetrieveAPIView):
    """GET /api/fitness/trainers/<id>/"""
    serializer_class = TrainerDetailSerializer
    permission_classes = (IsAuthenticated,)
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        return User.objects.filter(role='TRAINER').select_related('trainer_profile')


# --- 8. CLIENT DISCOVERY (trainer browses prospective clients) ---
class ClientListView(generics.ListAPIView):
    """GET /api/fitness/clients/?search=<q>  — Trainer/Admin only"""
    serializer_class = ClientListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if self.request.user.role not in ['TRAINER', 'ADMIN']:
            raise PermissionDenied("Only accounts with the Trainer role can browse clients.")

        already_clients = TrainerRelationship.objects.filter(
            trainer=self.request.user, is_active=True
        ).values_list('client_id', flat=True)

        queryset = User.objects.filter(role='USER').exclude(id__in=already_clients).select_related('profile')

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(profile__fitness_goal__icontains=search)
            )
        return queryset


# --- 9. TRAINER'S OWN PUBLIC PROFILE (onboarding writes here) ---
class TrainerProfileView(generics.RetrieveUpdateAPIView):
    """GET/POST/PATCH /api/fitness/trainer-profile/ — the logged-in trainer's own profile."""
    serializer_class = TrainerProfileSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        if self.request.user.role not in ['TRAINER', 'ADMIN']:
            raise PermissionDenied("Only trainers have a coaching profile.")
        profile, _ = TrainerProfile.objects.get_or_create(user=self.request.user)
        return profile

    def post(self, request, *args, **kwargs):
        # Onboarding calls POST; treat it the same as an update since the
        # profile row always exists once get_object() runs get_or_create.
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


# --- 10. CONNECTIONS (request -> accept/decline flow) ---
def _trainer_and_client_from_connection(connection):
    """Whichever side actually holds the TRAINER/ADMIN role becomes the
    trainer half of the resulting relationship/conversation."""
    if connection.from_user.role in ['TRAINER', 'ADMIN']:
        return connection.from_user, connection.to_user
    return connection.to_user, connection.from_user


class ConnectionRequestView(APIView):
    """POST /api/fitness/connections/request/  body: { to_user_id, note? }"""
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        to_user_id = request.data.get('to_user_id')
        if not to_user_id:
            raise ValidationError({"to_user_id": "This field is required."})
        if str(to_user_id) == str(request.user.id):
            raise ValidationError({"to_user_id": "You can't connect with yourself."})

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            raise NotFound("That user doesn't exist.")

        existing = Connection.objects.filter(
            Q(from_user=request.user, to_user=to_user) | Q(from_user=to_user, to_user=request.user),
            status='pending',
        ).first()
        if existing:
            return Response({"detail": "A request is already pending between you two."}, status=status.HTTP_400_BAD_REQUEST)

        connection = Connection.objects.create(
            from_user=request.user,
            to_user=to_user,
            note=request.data.get('note', ''),
        )
        return Response(ConnectionSerializer(connection, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ConnectionListView(generics.ListAPIView):
    """GET /api/fitness/connections/ — every connection involving the current user."""
    serializer_class = ConnectionSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return Connection.objects.filter(Q(from_user=user) | Q(to_user=user)).exclude(status='declined')


class ConnectionAcceptView(APIView):
    """POST /api/fitness/connections/<id>/accept/ — only the recipient can accept."""
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk, *args, **kwargs):
        connection = Connection.objects.filter(pk=pk, to_user=request.user, status='pending').first()
        if not connection:
            raise NotFound("No pending request found.")

        connection.status = 'accepted'
        connection.responded_at = timezone.now()
        connection.save()

        trainer_user, client_user = _trainer_and_client_from_connection(connection)

        relationship, _ = TrainerRelationship.objects.get_or_create(
            trainer=trainer_user,
            client=client_user,
            defaults={'is_active': True},
        )
        relationship.is_active = True
        relationship.save(update_fields=['is_active'])

        conversation, created = Conversation.objects.get_or_create(
            trainer=trainer_user,
            client=client_user,
            defaults={'connection': connection},
        )
        if not created and conversation.connection_id != connection.id:
            conversation.connection = connection
            conversation.save(update_fields=['connection'])

        return Response(ConnectionSerializer(connection, context={'request': request}).data, status=status.HTTP_200_OK)


class ConnectionDeclineView(APIView):
    """POST /api/fitness/connections/<id>/decline/ — only the recipient can decline."""
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk, *args, **kwargs):
        connection = Connection.objects.filter(pk=pk, to_user=request.user, status='pending').first()
        if not connection:
            raise NotFound("No pending request found.")

        connection.status = 'declined'
        connection.responded_at = timezone.now()
        connection.save()

        return Response({"message": "Request declined."}, status=status.HTTP_200_OK)


# --- 11. CONVERSATIONS & MESSAGES ---
class ConversationListView(generics.ListAPIView):
    """GET /api/fitness/conversations/"""
    serializer_class = ConversationListSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        user = self.request.user
        return Conversation.objects.filter(Q(trainer=user) | Q(client=user)).order_by('-created_at')


class ConversationMessagesView(generics.ListCreateAPIView):
    """
    GET  /api/fitness/conversations/<id>/messages/  — history (also used to seed the socket)
    POST /api/fitness/conversations/<id>/messages/  — fallback send if the websocket is down
    """
    serializer_class = MessageSerializer
    permission_classes = (IsAuthenticated,)

    def _get_conversation(self):
        conversation = Conversation.objects.filter(
            Q(pk=self.kwargs['pk']) & (Q(trainer=self.request.user) | Q(client=self.request.user))
        ).first()
        if not conversation:
            raise NotFound("Conversation not found.")
        return conversation

    def get_queryset(self):
        return self._get_conversation().messages.all()

    def create(self, request, *args, **kwargs):
        conversation = self._get_conversation()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(sender=request.user, conversation=conversation)

        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation.id}',
                {
                    'type': 'chat_message',
                    'id': message.id,
                    'conversation': conversation.id,
                    'sender': request.user.id,
                    'sender_id': request.user.id,
                    'text': message.text,
                    'created_at': message.created_at.isoformat(),
                }
            )
        except Exception:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)
