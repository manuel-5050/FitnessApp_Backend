import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import AIChatMessage
from ai_engine.services import get_ai_chat_reply


class AIChatConsumer(AsyncWebsocketConsumer):
    """
    One consumer instance per open WebSocket connection, scoped to the
    authenticated user's personal AI trainer chat. There's no conversation
    id anymore — every user has exactly one ongoing thread with the AI
    trainer. Messages are persisted immediately (so history survives
    reconnects/devices) and the AI reply is generated and streamed back
    over the same socket, using the Groq -> OpenAI -> fallback chain from
    ai_engine.services.
    """

    async def connect(self):
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f'ai_chat_{user.id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get('type') != 'message':
            return

        text = (data.get('text') or '').strip()
        if not text:
            return

        user = self.scope['user']

        # Persist + broadcast the user's own message first, so it appears
        # immediately (and on any other open tab/device for this user).
        user_message = await self._save_message(user, 'user', text)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'id': user_message.id,
                'role': 'user',
                'text': user_message.text,
                'created_at': user_message.created_at.isoformat(),
            },
        )

        # Let the client show a "PulseFit AI is typing..." indicator while
        # the LLM call is in flight.
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'typing_indicator', 'status': 'typing'},
        )

        history = await self._recent_history(user)
        reply_text = await self._generate_reply(text, history)

        ai_message = await self._save_message(user, 'assistant', reply_text)
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'id': ai_message.id,
                'role': 'assistant',
                'text': ai_message.text,
                'created_at': ai_message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event):
        """Group event handler — Channels dispatches here for every
        group_send with type 'chat_message', fanning it out to this socket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'id': event['id'],
            'role': event['role'],
            'text': event['text'],
            'created_at': event['created_at'],
        }))

    async def typing_indicator(self, event):
        """Group event handler for the 'AI is typing' status ping."""
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'status': event['status'],
        }))

    @database_sync_to_async
    def _save_message(self, user, role, text):
        return AIChatMessage.objects.create(user=user, role=role, text=text)

    @database_sync_to_async
    def _recent_history(self, user):
        messages = AIChatMessage.objects.filter(user=user).order_by('-created_at')[:10]
        # Reverse back to chronological order, reshaped for get_ai_chat_reply's
        # expected [{role, content}] history format.
        return [
            {'role': m.role, 'content': m.text}
            for m in reversed(list(messages))
        ]

    @sync_to_async
    def _generate_reply(self, text, history):
        return get_ai_chat_reply(text, history)
