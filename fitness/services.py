from ai_engine.services import AIFitnessEngine, generate_progress_insight as ai_generate_progress_insight
from .models import (
    WorkoutPlan,
    WorkoutSession,
    Exercise,
    DietPlan,
    Meal,
    DailyLog,
    WorkoutLog,
    MealLog,
    Alert,
    PersonalHealthProfile,
)
from django.utils import timezone


def generate_and_save_fitness_plans(profile_instance, burnout_alert=False, plateau_alert=False):
    """
    Calls the AI engine to generate plans for a user based on their PersonalHealthProfile,
    including adaptive flags for burnout and plateaus. Saves plans directly to PostgreSQL.
    """
    user = profile_instance.user

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

    engine = AIFitnessEngine()
    ai_plans = engine.generate_plans(
        profile_data,
        burnout_alert=burnout_alert,
        plateau_alert=plateau_alert
    )

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


def recompute_daily_nutrition_from_meals(user, date):
    """
    The 'smart calories' piece: sums every Meal the user has marked eaten
    (MealLog with completed=True) for a given date, from their currently
    active DietPlan, and writes the totals onto that day's DailyLog —
    calories_consumed, protein_consumed, carbs_consumed, fats_consumed.

    Called every time a meal gets marked eaten/un-eaten (fitness/views.py:
    MealLogListCreateView), so the daily log stays in sync automatically
    instead of requiring the user to type a calorie number by hand.

    A manual DailyLog entry (typed in directly) is left alone unless the
    user has at least one MealLog for that date — so days where they don't
    use meal-marking still work exactly as before.
    """
    logged_meals = MealLog.objects.filter(user=user, date=date, completed=True).select_related('meal')
    if not logged_meals.exists():
        return None

    totals = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
    for log in logged_meals:
        totals["calories"] += log.meal.calories or 0
        totals["protein"] += log.meal.protein or 0
        totals["carbs"] += log.meal.carbs or 0
        totals["fats"] += log.meal.fats or 0

    daily_log, _ = DailyLog.objects.get_or_create(user=user, date=date)
    daily_log.calories_consumed = totals["calories"]
    daily_log.protein_consumed = totals["protein"]
    daily_log.carbs_consumed = totals["carbs"]
    daily_log.fats_consumed = totals["fats"]
    daily_log.save(update_fields=[
        'calories_consumed', 'protein_consumed', 'carbs_consumed', 'fats_consumed'
    ])
    return daily_log


def daily_water_target_ml(profile):
    """35ml per kg of bodyweight — a standard clinical hydration guideline."""
    return round(profile.weight * 35)


def evaluate_health_signals(user):
    """
    Analyzes the user's chronological logging history to detect early signs
    of burnout, fitness plateaus, and chronic under-hydration — automatically
    generating system Alerts and triggering AI plan adjustments where relevant.

    Renamed from evaluate_burnout_and_plateau now that it also covers
    hydration, all three checks run from the same place since they're all
    driven off the same DailyLog save.
    """
    try:
        profile = PersonalHealthProfile.objects.get(user=user)
    except PersonalHealthProfile.DoesNotExist:
        return []

    alerts_triggered = []

    # --- 1. BURNOUT DETECTION ---
    recent_logs = list(DailyLog.objects.filter(user=user).order_by('-date')[:3])

    if len(recent_logs) == 3:
        fatigue_scores = [log.fatigue_level for log in recent_logs if log.fatigue_level is not None]
        if len(fatigue_scores) == 3 and all(score >= 8 for score in fatigue_scores):
            active_burnout = Alert.objects.filter(user=user, type='burnout', status='active').first()
            if not active_burnout:
                msg = "ALERT: High fatigue scores detected for 3 consecutive days. We have flagged a Burnout risk. Your workout and diet schedules have been automatically shifted to an Active Recovery & Deload plan."
                Alert.objects.create(user=user, type='burnout', status='active', message=msg)
                alerts_triggered.append(msg)
                generate_and_save_fitness_plans(profile, burnout_alert=True)

    # --- 2. PLATEAU DETECTION ---
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
                    Alert.objects.create(user=user, type='plateau', status='active', message=msg)
                    alerts_triggered.append(msg)
                    generate_and_save_fitness_plans(profile, plateau_alert=True)

    # --- 3. HYDRATION DETECTION ---
    # Three consecutive days under 50% of the target (35ml/kg bodyweight)
    # raises a soft warning. Unlike burnout/plateau this doesn't rewrite any
    # plan — there's nothing to regenerate, it's just a nudge.
    if len(recent_logs) == 3:
        target = daily_water_target_ml(profile)
        half_target = target / 2
        water_readings = [log.water_intake for log in recent_logs]
        if all(w is not None and w < half_target for w in water_readings):
            active_hydration = Alert.objects.filter(user=user, type='hydration', status='active').first()
            if not active_hydration:
                msg = f"ALERT: Water intake has stayed under {round(half_target)}ml (half your {target}ml target) for 3 days running. Low hydration can worsen fatigue and recovery — try to close the gap today."
                Alert.objects.create(user=user, type='hydration', status='active', message=msg)
                alerts_triggered.append(msg)

    return alerts_triggered


def generate_and_save_progress_insight(user, date):
    """
    Gathers the day's actual logged numbers (DailyLog) against the user's
    active DietPlan targets and today's workout completion, asks the AI
    engine for a short readable comment (ai_engine.services.
    generate_progress_insight), and saves it onto that day's DailyLog.

    Called after every DailyLog save and every meal-marking, so the "Against
    your targets" card on the dashboard always reflects the latest numbers.
    Returns the insight string, or None if there's nothing logged yet.
    """
    daily_log = DailyLog.objects.filter(user=user, date=date).first()
    if not daily_log:
        return None

    try:
        profile = PersonalHealthProfile.objects.get(user=user)
    except PersonalHealthProfile.DoesNotExist:
        profile = None

    diet_plan = DietPlan.objects.filter(user=user, is_active=True).first()
    target_water_ml = daily_water_target_ml(profile) if profile else None

    workout_completed_today = WorkoutLog.objects.filter(
        user=user, date=date, completed=True
    ).exists()

    context = {
        "fitness_goal": profile.fitness_goal if profile else "maintenance",
        "target_calories": diet_plan.target_calories if diet_plan else None,
        "target_protein": diet_plan.target_protein if diet_plan else None,
        "target_carbs": diet_plan.target_carbs if diet_plan else None,
        "target_fats": diet_plan.target_fats if diet_plan else None,
        "target_water_ml": target_water_ml,
        "calories_consumed": daily_log.calories_consumed,
        "protein_consumed": daily_log.protein_consumed,
        "carbs_consumed": daily_log.carbs_consumed,
        "fats_consumed": daily_log.fats_consumed,
        "water_intake": daily_log.water_intake,
        "weight_logged": daily_log.weight_logged,
        "fatigue_level": daily_log.fatigue_level,
        "workout_completed_today": workout_completed_today,
    }

    insight_text = ai_generate_progress_insight(context)

    daily_log.ai_insight = insight_text
    daily_log.save(update_fields=['ai_insight'])

    return insight_text
