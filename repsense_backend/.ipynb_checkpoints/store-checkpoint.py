"""
RepSense AI — User Profile Store
In-memory store with JSON file persistence. Swap for Redis/Postgres post-hackathon.
"""

import json
import os
from datetime import datetime, timedelta
from threading import Lock


DATA_FILE = "user_data.json"


class UserStore:
    """
    Thread-safe user profile store.

    Each user profile contains:
        name             str   — display name
        phone            str   — WhatsApp number (key)
        weight_kg        float — body weight
        goal             str   — muscle | fatloss | maintenance | endurance
        diet             str   — omnivore | vegetarian | vegan | hindu | halal | highprotein
        sessions_this_week int — resets every Monday
        total_sessions   int   — lifetime count
        last_session_date str  — ISO date of last logged workout
        reminders_on     bool  — daily reminder toggle
        joined           str   — ISO date joined
    """

    def __init__(self):
        self._lock = Lock()
        self._data: dict[str, dict] = {}
        self._load()

    def get_or_create(self, phone: str) -> dict:
        """Return existing profile or create a blank one."""
        with self._lock:
            if phone not in self._data:
                self._data[phone] = {
                    "phone":              phone,
                    "name":               "",
                    "weight_kg":          None,
                    "goal":               "",
                    "diet":               "",
                    "sessions_this_week": 0,
                    "total_sessions":     0,
                    "last_session_date":  None,
                    "reminders_on":       True,
                    "joined":             datetime.now().strftime("%Y-%m-%d"),
                }
                self._maybe_reset_weekly(self._data[phone])
            return self._data[phone]

    def save(self, phone: str, user: dict):
        """Persist the updated user dict."""
        with self._lock:
            self._data[phone] = user
            self._persist()

    def all_users(self) -> dict:
        """Return a copy of all user profiles (for reminders, debug)."""
        with self._lock:
            return dict(self._data)

    def _maybe_reset_weekly(self, user: dict):
        """Reset sessions_this_week if it's a new Monday since last session."""
        last = user.get("last_session_date")
        if not last:
            return
        try:
            last_dt   = datetime.fromisoformat(last)
            now       = datetime.now()
            last_mon  = last_dt - timedelta(days=last_dt.weekday())
            this_mon  = now     - timedelta(days=now.weekday())
            if this_mon > last_mon:
                user["sessions_this_week"] = 0
        except Exception:
            pass

    def _load(self):
        """Load persisted data from JSON file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    self._data = json.load(f)
                print(f"📂 Loaded {len(self._data)} user profile(s) from {DATA_FILE}")
            except Exception as e:
                print(f"⚠️  Could not load {DATA_FILE}: {e}")
                self._data = {}
        else:
            self._data = {}

    def _persist(self):
        """Write current data to JSON file (called inside lock)."""
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️  Could not save user data: {e}")
