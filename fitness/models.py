from django.db import models
from django.conf import settings

# 1. Personal Onboarding Health Profile
class PersonalHealthProfile(models.Model):
    GENDER_CHOICES = (
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    )

    ACTIVITY_CHOICES = (
        ('sedentary', 'Sedentary'),
        ('lightly_active', 'Lightly Active'),
        ('moderately_active', 'Moderately Active'),
        ('very_active', 'Very Active'),
    )

    GOAL_CHOICES = (
        ('weight_loss', 'Weight Loss'),
        ('muscle_gain', 'Muscle Gain'),
        ('endurance', 'Endurance'),
        ('maintenance', 'Maintenance'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='other')
    age = models.PositiveIntegerField()
    height = models.FloatField(help_text="Height in cm")
    weight = models.FloatField(help_text="Weight in kg")
    activity_level = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, default='moderately_active')
    fitness_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, default='maintenance')
    dietary_restrictions = models.JSONField(default=list, blank=True, help_text="List of dietary constraints")
    medical_conditions = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def bmi(self):
        if self.height and self.weight:
            height_m = self.height / 100.0
            return round(self.weight / (height_m ** 2), 2)
        return 0.0

    def __str__(self):
        return f"Profile of {self.user.email}"


# 2. Workout Schedules (Active / Inactive)
class WorkoutPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workout_plans')
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_workouts'
    )
    title = models.CharField(max_length=150)
    target_goal = models.CharField(max_length=100)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_ai_generated = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Automatically deactivate all other active workout plans of the user on saving this one
        if self.is_active:
            WorkoutPlan.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} for {self.user.email}"


class WorkoutSession(models.Model):
    workout_plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name='sessions')
    day_of_week = models.CharField(max_length=50, help_text="e.g. Monday, Tuesday")
    session_name = models.CharField(max_length=150, help_text="e.g. Push Day, Full Body Recovery")
    notes = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.day_of_week} - {self.session_name} ({self.workout_plan.user.email})"


class Exercise(models.Model):
    workout_session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='exercises')
    name = models.CharField(max_length=150)
    custom_gif_url = models.URLField(max_length=500, null=True, blank=True, help_text="Paste a custom exercise GIF link here")
    sets = models.PositiveIntegerField()
    reps = models.CharField(max_length=50, help_text="e.g. '10-12' or '15'")
    rest_time = models.CharField(max_length=50, help_text="e.g. '60s' or '90s'")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} - {self.sets}x{self.reps}"


# 3. Diet Schedules (Active / Inactive)
class DietPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diet_plans')
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_diets'
    )
    title = models.CharField(max_length=150)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_ai_generated = models.BooleanField(default=True)
    target_calories = models.PositiveIntegerField()
    target_protein = models.PositiveIntegerField(help_text="in grams")
    target_carbs = models.PositiveIntegerField(help_text="in grams")
    target_fats = models.PositiveIntegerField(help_text="in grams")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Automatically deactivate all other active diet plans of the user on saving this one
        if self.is_active:
            DietPlan.objects.filter(user=self.user, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} for {self.user.email}"


class Meal(models.Model):
    MEAL_TIME_CHOICES = (
        ('Breakfast', 'Breakfast'),
        ('Lunch', 'Lunch'),
        ('Dinner', 'Dinner'),
        ('Snack', 'Snack'),
    )

    diet_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE, related_name='meals')
    meal_time = models.CharField(max_length=50, choices=MEAL_TIME_CHOICES)
    name = models.CharField(max_length=150)
    custom_image_url = models.URLField(max_length=500, null=True, blank=True, help_text="Paste a custom food photo link here")
    food_items = models.TextField(help_text="Details of food components")
    calories = models.PositiveIntegerField(null=True, blank=True)
    protein = models.PositiveIntegerField(null=True, blank=True)
    carbs = models.PositiveIntegerField(null=True, blank=True)
    fats = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.meal_time}: {self.name} ({self.diet_plan.user.email})"


# 4. Daily Performance & Well-being Logs
class DailyLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_logs')
    date = models.DateField()
    weight_logged = models.FloatField(null=True, blank=True, help_text="Weight in kg")
    water_intake = models.PositiveIntegerField(default=0, help_text="Water in ml")
    calories_consumed = models.PositiveIntegerField(null=True, blank=True)
    fatigue_level = models.PositiveIntegerField(null=True, blank=True, help_text="Scale 1-10")
    notes = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"Log for {self.user.email} on {self.date}"


class WorkoutLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workout_logs')
    workout_session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name='logs')
    date = models.DateField()
    completed = models.BooleanField(default=True)
    duration_minutes = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'workout_session', 'date')
        ordering = ['-date']

    def __str__(self):
        status = "Completed" if self.completed else "Missed"
        return f"{self.user.email} - {self.workout_session.session_name} on {self.date} ({status})"


# 5. Burnout and Plateau Warnings
class Alert(models.Model):
    ALERT_TYPES = (
        ('burnout', 'Burnout Warning'),
        ('plateau', 'Plateau Warning'),
    )

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('resolved', 'Resolved'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    type = models.CharField(max_length=15, choices=ALERT_TYPES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_type_display()} ({self.status}) for {self.user.email}"


# 6. Trainer-Client Mappings
class TrainerRelationship(models.Model):
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clients'
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainers'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('trainer', 'client')

    def __str__(self):
        return f"Trainer {self.trainer.email} -> Client {self.client.email}"

# 7. Public-facing trainer profile (browsable by clients on /find-trainer)
class TrainerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainer_profile'
    )
    bio = models.TextField(blank=True, default='')
    specialties = models.JSONField(default=list, blank=True)
    years_experience = models.PositiveIntegerField(null=True, blank=True)
    certifications = models.JSONField(default=list, blank=True, help_text="List of certification names")
    rating = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Trainer profile for {self.user.email}"


# 8. Trainer <-> Client connection requests (browse -> request -> accept flow)
class Connection(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_connections'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_connections'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.from_user.email} -> {self.to_user.email} ({self.status})"


# 9. A trainer<->client message thread, created once a Connection is accepted
class Conversation(models.Model):
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trainer_conversations'
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_conversations'
    )
    connection = models.OneToOneField(
        Connection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversation'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('trainer', 'client')

    def __str__(self):
        return f"Conversation: {self.trainer.email} <-> {self.client.email}"


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.email}: {self.text[:40]}"
