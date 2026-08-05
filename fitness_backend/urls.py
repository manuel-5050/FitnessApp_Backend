"""
URL configuration for fitness_backend project.
"""
from django.contrib import admin
from django.urls import path, include

# --- CUSTOM BRANDING FOR DJANGO ADMIN PANEL ---
admin.site.site_header = "AI Personal Health & Fitness Admin Portal"
admin.site.site_title = "Sandra's AI Fitness Portal"
admin.site.index_title = "Welcome to the AI Health & Fitness Management Administration Console"

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth routing
    path('api/auth/', include('accounts.urls')),
    
    # Fitness & AI routing
    path('api/fitness/', include('fitness.urls')),
    path('api/ai/', include('ai_engine.urls')),
]
