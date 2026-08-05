import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db.models import Q

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    """
    One consumer instance per open WebSocket connection, scoped to a single
    conversation. Messages sent here are persisted to Postgres immediately
    (so REST history via ConversationMessagesView stays consistent) and then
    broadcast to every connection subscribed to the same conversation's group.
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f'chat_{self.conversation_id}'
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        is_participant = await self._user_is_participant(user, self.conversation_id)
        if not is_participant:
            await self.close(code=4003)
            return

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
        message = await self._save_message(user, self.conversation_id, text)

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat_message',
                'id': message.id,
                'conversation': int(self.conversation_id),
                'sender': user.id,
                'sender_id': user.id,
                'text': message.text,
                'created_at': message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event):
        """Group event handler — Channels dispatches here for every
        group_send with type 'chat_message', fanning it out to this socket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'id': event['id'],
            'conversation': event['conversation'],
            'sender': event.get('sender', event['sender_id']),
            'sender_id': event['sender_id'],
            'text': event['text'],
            'created_at': event['created_at'],
        }))

    @database_sync_to_async
    def _user_is_participant(self, user, conversation_id):
        return Conversation.objects.filter(
            id=conversation_id
        ).filter(
            Q(trainer=user) | Q(client=user)
        ).exists()

    @database_sync_to_async
    def _save_message(self, user, conversation_id, text):
        conversation = Conversation.objects.get(id=conversation_id)
        return Message.objects.create(conversation=conversation, sender=user, text=text)


