from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Defining our User Roles as text options.
    # TRAINER role removed — PulseFit AI now uses a single AI trainer,
    # with only USER and ADMIN as human account roles.
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        USER = 'USER', 'User'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.USER)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    # Use email as the main username identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
