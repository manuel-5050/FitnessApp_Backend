from ai_engine.services import AIFitnessEngine
from .models import WorkoutPlan, WorkoutSession, Exercise, DietPlan, Meal, DailyLog, WorkoutLog, Alert, PersonalHealthProfile
from django.utils import timezone

def generate_and_save_fitness_plans(profile_instance, burnout_alert=False, plateau_alert=False):
    """
    Calls the AI engine to generate plans for a user based on their PersonalHealthProfile,
    including adaptive flags for burnout and plateaus. Saves plans directly to PostgreSQL.
    """
    user = profile_instance.user
    
    # 1. Structure the profile data for the AI engine
    profile_data = {
        "gender": profile_instance.gender,
        "age": profile_instance.age,
        "height": profile_instance.height,
        "weight": profile_instance.weight,
        "activity_level": profile_instance.activity_level,
        "fitness_goal": profile_instance.fitness_goal,
        "dietary_restrictions": profile_instance.dietary_restrictions,
        "medical_conditions": profile_instance.medical_conditions
    }
    
    # 2. Call the AI Fitness Engine
    engine = AIFitnessEngine()
    ai_plans = engine.generate_plans(
        profile_data,
        burnout_alert=burnout_alert,
        plateau_alert=plateau_alert
    )
    
    # 3. Save the Workout Plan
    workout_data = ai_plans.get('workout_plan', {})
    if workout_data:
        workout_plan = WorkoutPlan.objects.create(
            user=user,
            title=workout_data.get('title', 'AI Customized Workout Plan'),
            target_goal=workout_data.get('target_goal', profile_instance.fitness_goal),
            is_active=True,
            is_ai_generated=True
        )
        
        for session_data in workout_data.get('weekly_sessions', []):
            session = WorkoutSession.objects.create(
                workout_plan=workout_plan,
                day_of_week=session_data.get('day_of_week', 'Monday'),
                session_name=session_data.get('session_name', 'General Workout')
            )
            
            for idx, ex_data in enumerate(session_data.get('exercises', [])):
                Exercise.objects.create(
                    workout_session=session,
                    name=ex_data.get('name', 'Exercise'),
                    sets=int(ex_data.get('sets', 3)),
                    reps=str(ex_data.get('reps', '10')),
                    rest_time=str(ex_data.get('rest_time', '60s')),
                    order=idx
                )
                
    # 4. Save the Diet Plan
    diet_data = ai_plans.get('diet_plan', {})
    if diet_data:
        diet_plan = DietPlan.objects.create(
            user=user,
            title=diet_data.get('title', 'AI Customized Diet Plan'),
            is_active=True,
            is_ai_generated=True,
            target_calories=int(diet_data.get('target_calories', 2000)),
            target_protein=int(diet_data.get('target_protein', 130)),
            target_carbs=int(diet_data.get('target_carbs', 220)),
            target_fats=int(diet_data.get('target_fats', 65))
        )
        
        for meal_data in diet_data.get('meals', []):
            Meal.objects.create(
                diet_plan=diet_plan,
                meal_time=meal_data.get('meal_time', 'Breakfast'),
                name=meal_data.get('name', 'Healthy Meal'),
                food_items=meal_data.get('food_items', 'Clean food'),
                calories=meal_data.get('calories'),
                protein=meal_data.get('protein'),
                carbs=meal_data.get('carbs'),
                fats=meal_data.get('fats')
            )


def evaluate_burnout_and_plateau(user):
    """
    Analyzes the user's chronological logging history to detect early signs
    of burnout or fitness plateaus, automatically generating system Alerts
    and triggering AI plan adjustments.
    """
    try:
        profile = PersonalHealthProfile.objects.get(user=user)
    except PersonalHealthProfile.DoesNotExist:
        return []

    alerts_triggered = []

    # --- 1. BURNOUT DETECTION ---
    # Check if user has logged high fatigue (fatigue_level >= 8) for the 3 most recent consecutive days
    recent_logs = list(DailyLog.objects.filter(user=user).order_by('-date')[:3])
    
    if len(recent_logs) == 3:
        fatigue_scores = [log.fatigue_level for log in recent_logs if log.fatigue_level is not None]
        if len(fatigue_scores) == 3 and all(score >= 8 for score in fatigue_scores):
            # Trigger Burnout Alert if not already active
            active_burnout = Alert.objects.filter(user=user, type='burnout', status='active').first()
            if not active_burnout:
                msg = "ALERT: High fatigue scores detected for 3 consecutive days. We have flagged a Burnout risk. Your workout and diet schedules have been automatically shifted to an Active Recovery & Deload plan."
                Alert.objects.create(
                    user=user,
                    type='burnout',
                    status='active',
                    message=msg
                )
                alerts_triggered.append(msg)
                # Regenerate plans with burnout deload active!
                generate_and_save_fitness_plans(profile, burnout_alert=True)

    # --- 2. PLATEAU DETECTION ---
    # Check if weight has stalled (< 0.1kg change) in the last 14 days over 3 or more weigh-ins
    fourteen_days_ago = timezone.now().date() - timezone.timedelta(days=14)
    logs_14d = list(DailyLog.objects.filter(user=user, date__gte=fourteen_days_ago).order_by('-date'))
    
    if len(logs_14d) >= 3:
        weights = [log.weight_logged for log in logs_14d if log.weight_logged is not None]
        if len(weights) >= 3:
            weight_diff = abs(weights[0] - weights[-1])
            if weight_diff < 0.1:
                active_plateau = Alert.objects.filter(user=user, type='plateau', status='active').first()
                if not active_plateau:
                    msg = "ALERT: We detected a progress plateau over the last 14 days. Your body has adapted to your current energy and training balance. Your schedules have been automatically updated to a Plateau-Breaker protocol to shock your metabolism!"
                    Alert.objects.create(
                        user=user,
                        type='plateau',
                        status='active',
                        message=msg
                    )
                    alerts_triggered.append(msg)
                    # Regenerate plans with plateau breaker active!
                    generate_and_save_fitness_plans(profile, plateau_alert=True)

    return alerts_triggered