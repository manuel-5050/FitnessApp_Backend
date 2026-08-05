from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

# Serializer to safely display user details (hides sensitive fields like password hashes)
class UserSerializer(serializers.ModelSerializer):
    has_completed_onboarding = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'has_completed_onboarding')
        read_only_fields = ('id', 'role')

    def get_has_completed_onboarding(self, user):
        if user.role in [User.Role.TRAINER, User.Role.ADMIN]:
            return hasattr(user, 'trainer_profile') and bool(user.trainer_profile.bio or user.trainer_profile.specialties)
        return hasattr(user, 'profile')

# Serializer to handle user sign-ups
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'role', 'phone_number', 'password')
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    # Custom create method to cleanly hash the password and match email to username
    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.get('role', User.Role.USER)
        
        user = User.objects.create_user(
            username=validated_data['email'],  # Django's AbstractUser requires a unique username
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=role,
            phone_number=validated_data.get('phone_number', ''),
            password=password
        )
        return user