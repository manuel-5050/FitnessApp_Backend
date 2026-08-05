from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import get_ai_chat_reply


class AIChatView(APIView):
    """
    POST /api/ai/chat/
    body: { message: str, history?: [{role: "user"|"assistant", content: str}] }
    -> { reply: str }

    Powers both the floating AIChatWidget and the "PulseFit AI" tab inside
    the Chat page on the frontend — reuses AIFitnessEngine's Groq/OpenAI/
    fallback chain (ai_engine.services) but for conversational replies
    instead of structured workout/diet JSON.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        message = (request.data.get('message') or '').strip()
        if not message:
            return Response({"detail": "message is required."}, status=status.HTTP_400_BAD_REQUEST)

        history = request.data.get('history', [])
        if not isinstance(history, list):
            history = []

        reply = get_ai_chat_reply(message, history)
        return Response({"reply": reply}, status=status.HTTP_200_OK)
