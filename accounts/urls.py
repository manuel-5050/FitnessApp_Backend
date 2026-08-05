from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, UserMeView

urlpatterns = [
    # 1. Registration endpoint: POST /api/auth/register/
    path('register/', RegisterView.as_view(), name='auth_register'),
    
    # 2. Login endpoint (returns access & refresh JWT tokens): POST /api/auth/token/
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # 3. Token refresh endpoint: POST /api/auth/token/refresh/
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # 4. Fetch current user details: GET /api/auth/me/
    path('me/', UserMeView.as_view(), name='auth_me'),
]