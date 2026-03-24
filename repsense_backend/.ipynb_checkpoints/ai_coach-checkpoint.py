"""
RepSense AI — Claude-Powered Fitness Coach
Processes WhatsApp messages and generates personalised coaching responses.
"""

import os
import json
import re
from anthropic import AsyncAnthropic
from datetime import datetime


SYSTEM_PROMPT = """You are RepSense AI — an intelligent fitness coach and nutrition advisor available via WhatsApp.

Your personality: encouraging, knowledgeable, concise. You speak like a friendly personal trainer — not robotic.

You help users with:
1. **Workout logging** — Parse what they trained and give feedback + rep/set tracking
2. **Form tips** — Evidence-based technique advice for exercises
3. **Nutrition** — Personalised meal plans respecting cultural/dietary preferences
4. **Supplements** — Evidence-based guidance (always recommend consulting a doctor)
5. **Progress tracking** — Weekly summaries, motivational insights
6. **Profile setup** — Collect weight, goal, diet type when user first starts

FORMATTING RULES (WhatsApp markdown):
- Use *bold* for key numbers and exercise names
- Use _italic_ for tips and insights
- Use bullet points with • (not dashes)
- Keep replies under 300 words — WhatsApp is a chat, not an essay
- Use 1-2 relevant emojis per message, sparingly
- Never use triple backticks or HTML

WORKOUT PARSING:
When a user logs a workout (e.g. "squats 4x10", "did bench press 3 sets of 8 at 60kg"):
1. Confirm what you heard with exact numbers
2. Give ONE specific form tip for that exercise
3. Mention how it contributes to their goal
4. Update their session count in your response (include the JSON block)

PROFILE SETUP (first message or /setup):
Ask for: name, weight (kg), goal (muscle/fat loss/maintenance/endurance), diet type
Store as JSON in your response.

USER PROFILE CONTEXT:
You will receive the user's current profile as a JSON block at the start of each conversation.
Use this to personalise ALL responses.

SPECIAL COMMANDS:
• /setup — Collect user profile
• /stats — Show this week's sessions and progress
• /nutrition — Generate today's full meal plan
• /supplements — Show supplement recommendations for their goal
• /reminders on|off — Toggle daily reminders
• /reset — Clear their profile

RESPONSE FORMAT:
Always end your reply with a JSON block (hidden from user — enclosed in <<<JSON>>> tags)
containing any profile updates:

<<<JSON>>>
{
  "profile_updates": {
    "name": "optional",
    "weight_kg": 0,
    "goal": "muscle|fatloss|maintenance|endurance",
    "diet": "omnivore|vegetarian|vegan|hindu|halal|highprotein",
    "reminders_on": true
  },
  "session_logged": true,
  "sessions_increment": 1
}
<<<END>>>

Only include fields that changed. If nothing changed, omit the JSON block entirely.
"""


class AICoach:
    """
    Handles all AI logic for the RepSense WhatsApp coach.
    Uses Claude claude-haiku-4-5-20251001 for speed and cost efficiency in hackathon context.
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        self.client = AsyncAnthropic(api_key=api_key)
        self.model  = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

    async def handle_message(self, user: dict, message: str) -> str:
        """
        Process an incoming WhatsApp message and return the coach's reply.

        Args:
            user:    The user's profile dict from UserStore
            message: The raw text from WhatsApp
        """
        # Handle special commands locally (faster, no API call)
        lower = message.lower().strip()

        if lower in ("/help", "help", "hi", "hello", "hey"):
            return self._welcome_message(user)

        if lower == "/stats":
            return self._stats_message(user)

        if lower.startswith("/reminders"):
            return self._toggle_reminders(user, lower)

        if lower == "/reset":
            user.clear()
            return "✅ Profile reset! Send *hello* to start fresh."

        # Build conversation for Claude
        profile_context = self._format_profile(user)

        messages = [
            {
                "role": "user",
                "content": f"{profile_context}\n\nUser message: {message}"
            }
        ]

        # Call Claude
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            raw_reply = response.content[0].text

        except Exception as e:
            print(f"❌ Claude API error: {e}")
            return "Sorry, I'm having a moment! Try again in a few seconds 🙏"

        # Parse out hidden JSON profile updates
        reply, updates = self._extract_json_updates(raw_reply)

        # Apply profile updates
        if updates:
            self._apply_updates(user, updates)

        return reply.strip()

    def _format_profile(self, user: dict) -> str:
        """Format the user profile as context for Claude."""
        if not user:
            return "User profile: NEW USER — no profile yet."

        return (
            f"User profile:\n"
            f"• Name: {user.get('name', 'Unknown')}\n"
            f"• Weight: {user.get('weight_kg', '?')} kg\n"
            f"• Goal: {user.get('goal', 'not set')}\n"
            f"• Diet: {user.get('diet', 'not set')}\n"
            f"• Sessions this week: {user.get('sessions_this_week', 0)}\n"
            f"• Total sessions: {user.get('total_sessions', 0)}\n"
            f"• Member since: {user.get('joined', 'today')}"
        )

    def _extract_json_updates(self, raw: str) -> tuple[str, dict]:
        """Strip the hidden JSON block from Claude's reply and parse it."""
        json_pattern = r"<<<JSON>>>(.*?)<<<END>>>"
        match = re.search(json_pattern, raw, re.DOTALL)

        if not match:
            return raw, {}

        clean_reply = raw[:match.start()].strip()
        try:
            data = json.loads(match.group(1).strip())
            return clean_reply, data
        except json.JSONDecodeError:
            return clean_reply, {}

    def _apply_updates(self, user: dict, updates: dict):
        """Apply profile updates from Claude's response."""
        profile_updates = updates.get("profile_updates", {})
        for key, val in profile_updates.items():
            if val not in (None, "", 0):
                user[key] = val

        # Increment session count if a workout was logged
        if updates.get("session_logged") and updates.get("sessions_increment", 0) > 0:
            user["sessions_this_week"] = user.get("sessions_this_week", 0) + 1
            user["total_sessions"]     = user.get("total_sessions", 0) + 1

            # Record today's date for streak tracking
            user["last_session_date"] = datetime.now().strftime("%Y-%m-%d")

    def _welcome_message(self, user: dict) -> str:
        name = user.get("name", "")
        greeting = f"Hey {name}! 👋" if name else "Hey! 👋 Welcome to RepSense AI"

        return (
            f"{greeting}\n\n"
            f"I'm your AI fitness coach. Here's what I can do:\n\n"
            f"💪 *Log workouts* — _'squats 4x10 at 80kg'_\n"
            f"🥗 *Nutrition plan* — /nutrition\n"
            f"📊 *Your stats* — /stats\n"
            f"💊 *Supplement guide* — /supplements\n"
            f"⚙️ *Set up profile* — /setup\n"
            f"🔔 *Toggle reminders* — /reminders on|off\n\n"
            f"What did you train today? 🏋️"
        )

    def _stats_message(self, user: dict) -> str:
        sessions = user.get("sessions_this_week", 0)
        total    = user.get("total_sessions", 0)
        goal     = user.get("goal", "your goal")
        name     = user.get("name", "")

        emojis = ["🔥", "💪", "⚡", "🏆", "🎯"]
        emoji  = emojis[min(sessions, len(emojis) - 1)]

        return (
            f"{emoji} *This week's stats{' for ' + name if name else ''}:*\n\n"
            f"• Sessions this week: *{sessions}*\n"
            f"• Total sessions ever: *{total}*\n"
            f"• Goal: *{goal}*\n\n"
            f"{'Great consistency! Keep it up 🔥' if sessions >= 3 else 'Still time to hit your weekly target! 💪'}\n\n"
            f"_Tip: reply with what you trained to log it._"
        )

    def _toggle_reminders(self, user: dict, command: str) -> str:
        if "off" in command:
            user["reminders_on"] = False
            return "🔕 Daily reminders turned *off*. You can turn them back on with /reminders on"
        else:
            user["reminders_on"] = True
            return "🔔 Daily reminders turned *on*! You'll hear from me every morning at 7am 💪"
