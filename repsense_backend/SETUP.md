# RepSense AI — WhatsApp Backend Setup Guide

## What you'll have running

```
WhatsApp user → Meta Cloud API → your /webhook → Claude AI → reply back
```

---

## Prerequisites

- Python 3.10+
- An **Anthropic API key** — https://console.anthropic.com
- A **Meta Developer account** — https://developers.facebook.com
- **ngrok** (for local dev) — https://ngrok.com/download

---

## Step 1 — Install dependencies

```bash
cd repsense_backend
pip install -r requirements.txt
```

---

## Step 2 — Configure environment

```bash
cp .env.example .env
# Edit .env with your keys (see Step 4 for WhatsApp keys)
```

Add your Anthropic key immediately:
```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

---

## Step 3 — Expose your local server with ngrok

In a **new terminal window**:
```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL, e.g.:
```
https://abc123.ngrok-free.app
```

This is your **Webhook URL** — keep this terminal open!

---

## Step 4 — Set up Meta / WhatsApp

### 4a. Create a Meta App

1. Go to https://developers.facebook.com/apps
2. Click **Create App**
3. Select **Business** type
4. Give it a name (e.g. "RepSense AI")

### 4b. Add WhatsApp product

1. In your app dashboard → **Add Product** → **WhatsApp**
2. Click **Set Up**

### 4c. Get your credentials

In **WhatsApp → API Setup**:
- Copy **Phone Number ID** → paste into `.env` as `WHATSAPP_PHONE_NUMBER_ID`
- Copy **Temporary Access Token** → paste into `.env` as `WHATSAPP_ACCESS_TOKEN`

> 💡 For production: create a **System User** token (doesn't expire) via Business Settings

### 4d. Add a test phone number

Still in **API Setup**:
1. Under *To*, add your personal WhatsApp number
2. Send a test message to verify it works

### 4e. Configure the Webhook

1. In your app dashboard → **WhatsApp → Configuration**
2. Click **Edit** next to Webhook
3. Set:
   - **Callback URL**: `https://abc123.ngrok-free.app/webhook`
   - **Verify Token**: `repsense_verify_token` (must match `.env`)
4. Click **Verify and Save**
5. Under **Webhook Fields**, subscribe to: `messages`

---

## Step 5 — Start the server

```bash
uvicorn main:app --reload --port 8000
```

You should see:
```
✅ RepSense AI backend started. Scheduler running.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 6 — Test it!

Send a WhatsApp message to your test number:
```
hello
```

You should get back the welcome message from RepSense AI 🎉

### Try these example messages:
| Message | What happens |
|---|---|
| `hello` | Welcome message + menu |
| `/setup` | Profile setup flow |
| `squats 4x10 at 80kg` | Workout logged + form tip |
| `just did 20 push-ups` | Logged + technique advice |
| `/nutrition` | Full day meal plan for your diet type |
| `/supplements` | Supplement guide for your goal |
| `/stats` | Weekly session count |
| `/reminders off` | Disable 7am reminders |

---

## Architecture Overview

```
main.py              FastAPI app — webhook handler, scheduler
whatsapp_client.py   Async HTTP client for Meta Graph API
ai_coach.py          Claude integration — message routing + prompt engineering
store.py             JSON-backed user profile store
```

---

## Deploying to production (post-hackathon)

Replace ngrok with a real server:

**Option A — Railway (easiest)**
```bash
railway init
railway up
```

**Option B — Render**
- Connect your GitHub repo
- Set env vars in Render dashboard
- Deploy

**Option C — AWS Lambda + API Gateway**
- Use Mangum adapter: `pip install mangum`
- Add `handler = Mangum(app)` to main.py

Then update your Webhook URL in Meta Dashboard to your production URL.

---

## Upgrading the token (important!)

The temporary token expires in **24 hours**. Before demo day:

1. Go to **Business Settings** → **System Users** → **Add**
2. Create a system user with **FULL_CONTROL** on your WhatsApp app
3. Generate a **permanent token** with `whatsapp_business_messaging` permission
4. Update `WHATSAPP_ACCESS_TOKEN` in your `.env`
