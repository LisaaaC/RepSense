"""
RepSense AI — WhatsApp Backend
FastAPI app: handles Meta webhook verification + incoming message routing
"""

import os
import json
import asyncio
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from whatsapp_client import WhatsAppClient
from ai_coach import AICoach
from store import UserStore

load_dotenv()

# ── Globals ──────────────────────────────────────────────────────────────
wa        = WhatsAppClient()
coach     = AICoach()
store     = UserStore()
scheduler = AsyncIOScheduler()

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "repsense_verify_token")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule daily workout reminder at 07:00
    scheduler.add_job(
        send_daily_reminders,
        trigger="cron",
        hour=7,
        minute=0,
        id="daily_reminder",
        replace_existing=True,
    )
    scheduler.start()
    print("✅ RepSense AI backend started. Scheduler running.")
    yield
    scheduler.shutdown()
    print("🛑 Scheduler stopped.")


app = FastAPI(title="RepSense AI Backend", version="1.0.0", lifespan=lifespan)


# ── Webhook: GET (Meta verification challenge) ────────────────────────────
@app.get("/webhook")
async def verify_webhook(
    request: Request,
):
    params = dict(request.query_params)
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print(f"✅ Webhook verified. Challenge: {challenge}")
        return PlainTextResponse(content=challenge)

    print(f"❌ Webhook verification failed. Token received: {token}")
    return Response(status_code=403)


# ── Webhook: POST (incoming WhatsApp messages) ────────────────────────────
@app.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks):
    try:
        data = await request.json()
    except Exception:
        return Response(status_code=400)

    # Meta always expects a 200 immediately
    background.add_task(process_webhook_payload, data)
    return Response(status_code=200)


async def process_webhook_payload(data: dict):
    """Extract message details and route to the AI coach."""
    try:
        entry   = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value   = changes.get("value", {})

        messages = value.get("messages", [])
        if not messages:
            return  # status updates, read receipts — ignore

        msg          = messages[0]
        from_number  = msg.get("from")          # sender's WhatsApp number
        msg_type     = msg.get("type", "text")
        message_id   = msg.get("id")

        # Only handle text messages for MVP
        if msg_type == "text":
            body = msg["text"]["body"].strip()
        elif msg_type == "image":
            # Future: send image to vision model
            await wa.send_text(from_number, "📸 Image received! Vision analysis is coming in MVP+ — for now, describe your meal or exercise and I'll analyse it.")
            return
        else:
            return

        print(f"📩 Message from {from_number}: {body}")

        # Get or create user profile
        user = store.get_or_create(from_number)

        # Mark as typing (status indicator)
        await wa.send_reaction(from_number, message_id, "💪")

        # Route to AI coach
        reply = await coach.handle_message(user, body)

        # Persist any profile updates
        store.save(from_number, user)

        # Send reply
        await wa.send_text(from_number, reply)

    except Exception as e:
        print(f"❌ Error processing message: {e}")


# ── Scheduled: daily reminders ─────────────────────────────────────────────
async def send_daily_reminders():
    """Send personalised morning reminders to all active users."""
    users = store.all_users()
    print(f"⏰ Sending daily reminders to {len(users)} users...")

    for phone, user in users.items():
        if not user.get("reminders_on", True):
            continue
        try:
            goal     = user.get("goal", "your fitness goal")
            name     = user.get("name", "there")
            sessions = user.get("sessions_this_week", 0)

            reminder = (
                f"Good morning, {name}! 🌅\n\n"
                f"You've trained *{sessions}* time(s) this week — keep it going!\n\n"
                f"💪 Today's tip: Stay consistent with your *{goal}* goal. "
                f"Even 20 minutes beats zero.\n\n"
                f"Reply with what you trained today or ask me anything:\n"
                f"• _'just did squats 4x10'_\n"
                f"• _'what should I eat today?'_\n"
                f"• _'how am I doing this week?'_"
            )
            await wa.send_text(phone, reminder)
        except Exception as e:
            print(f"  ⚠️ Could not send reminder to {phone}: {e}")


# ── Health check ──────────────────────────────────────────────────────────
@app.get("/")
async def health():
    return {"status": "RepSense AI backend is running 🏋️", "version": "1.0.0"}


@app.get("/users")
async def list_users():
    """Debug endpoint: list all user profiles."""
    return {"users": store.all_users()}
