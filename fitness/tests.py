from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class FitnessEndpointEmptyStateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="strong-password-123",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)

    def test_profile_returns_empty_object_when_missing(self):
        response = self.client.get("/api/fitness/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {})

    def test_workout_plan_returns_empty_object_when_missing(self):
        response = self.client.get("/api/fitness/plans/workout/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {})

    def test_diet_plan_returns_empty_object_when_missing(self):
        response = self.client.get("/api/fitness/plans/diet/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {})
