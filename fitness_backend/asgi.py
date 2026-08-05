"""
ASGI config for fitness_backend project.

Serves plain HTTP requests through Django as usual, and routes anything
under /ws/ to Channels for the trainer<->client chat. JWTAuthMiddleware
(fitness/channels_auth.py) reads the ?token= query param on the WebSocket
URL so consumers see request.user the same way DRF views do.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fitness_backend.settings')

# get_asgi_application() must run before importing anything that touches
# models/apps (Channels routing does, via consumers.py), or Django raises
# AppRegistryNotReady.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from fitness.channels_auth import JWTAuthMiddleware  # noqa: E402
from fitness.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
