"""
Channels doesn't know about DRF/SimpleJWT auth out of the box — WebSocket
connections don't carry an Authorization header the way normal fetches do,
so the frontend (see src/api/socket.js) puts the access token on the query
string instead: ws://.../ws/chat/<id>/?token=<accessToken>

This middleware pulls that token out, validates it exactly the way
JWTAuthentication does for regular API views, and attaches the resulting
user to scope["user"] so consumers can use it like request.user.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


@database_sync_to_async
def _get_user_from_token(token):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        validated_token = AccessToken(token)
        user_id = validated_token['user_id']
        return User.objects.get(id=user_id)
    except (TokenError, KeyError, Exception):
        return AnonymousUser()


class JWTAuthMiddleware:
    """ASGI middleware — wraps the inner application (URLRouter) and injects
    scope["user"] before the connection reaches a consumer."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        scope['user'] = await _get_user_from_token(token) if token else AnonymousUser()

        return await self.inner(scope, receive, send)
