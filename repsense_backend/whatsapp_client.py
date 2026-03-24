"""
RepSense AI — WhatsApp Business Cloud API Client
Wraps Meta's Graph API for sending messages and reactions.
"""

import os
import httpx
from typing import Optional


class WhatsAppClient:
    """
    Thin async client for the WhatsApp Business Cloud API.

    Env vars required:
      WHATSAPP_PHONE_NUMBER_ID  — from Meta Developer Dashboard → App → WhatsApp → API Setup
      WHATSAPP_ACCESS_TOKEN     — temporary token (24h) or permanent System User token
    """

    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self):
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.access_token    = os.getenv("WHATSAPP_ACCESS_TOKEN")

        if not self.phone_number_id or not self.access_token:
            print("⚠️  WhatsApp credentials not set. Messages will be logged only.")

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json",
        }

    @property
    def _messages_url(self) -> str:
        return f"{self.BASE_URL}/{self.phone_number_id}/messages"

    async def send_text(self, to: str, body: str) -> dict:
        """Send a plain text message. Supports WhatsApp markdown (*bold*, _italic_, ~strikethrough~)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type":    "individual",
            "to":                to,
            "type":              "text",
            "text": {
                "preview_url": False,
                "body":        body,
            },
        }
        return await self._post(payload)

    async def send_reaction(self, to: str, message_id: str, emoji: str) -> dict:
        """React to a specific message with an emoji."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type":    "individual",
            "to":                to,
            "type":              "reaction",
            "reaction": {
                "message_id": message_id,
                "emoji":      emoji,
            },
        }
        return await self._post(payload)

    async def send_template(self, to: str, template_name: str, language: str = "en_US", components: Optional[list] = None) -> dict:
        """
        Send a pre-approved WhatsApp template message.
        Required for outbound messages to users who haven't messaged first in 24h.
        """
        payload = {
            "messaging_product": "whatsapp",
            "to":                to,
            "type":              "template",
            "template": {
                "name":     template_name,
                "language": {"code": language},
                **({"components": components} if components else {}),
            },
        }
        return await self._post(payload)

    async def send_interactive_buttons(self, to: str, body: str, buttons: list[dict]) -> dict:
        """
        Send a message with up to 3 quick-reply buttons.

        Example buttons:
            [
                {"id": "btn_workout", "title": "Log Workout"},
                {"id": "btn_nutrition", "title": "Nutrition Plan"},
                {"id": "btn_stats",   "title": "My Stats"},
            ]
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type":    "individual",
            "to":                to,
            "type":              "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                        for b in buttons[:3]
                    ]
                },
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict) -> dict:
        """Send a request to the Graph API."""
        if not self.phone_number_id or not self.access_token:
            print(f"📤 [MOCK] Would send to {payload.get('to')}: {payload}")
            return {"status": "mock"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(self._messages_url, json=payload, headers=self._headers)

        if resp.status_code not in (200, 201):
            print(f"❌ WhatsApp API error {resp.status_code}: {resp.text}")
        else:
            print(f"✅ Message sent to {payload.get('to')}")

        return resp.json()
