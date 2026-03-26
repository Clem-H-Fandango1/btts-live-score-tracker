import datetime
import json
import os

import pytz
from flask import Flask, jsonify, render_template, request, session, redirect
# Application version string.  Incremented when new features are added.
APP_VERSION = "v2.2.1"
import requests
from typing import Any, Dict, List, Optional


app = Flask(__name__, static_folder="static", template_folder="templates")

# Secret key for session management (e.g. admin login).  In a production
# deployment, this should be set via an environment variable and kept
# secret.  A default is provided here for convenience.
app.secret_key = os.environ.get("SECRET_KEY", "bttssecretkey")

# Admin password for login.  This should also be set via an environment
# variable in production.  The default can be overridden by setting
# ADMIN_PASSWORD when running the container or application.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Password for accessing the BTTS odds page.  This is separate from the
# administrator password to allow sharing predictions without granting
# administrative privileges.  In production, override via the
# ODDS_PASSWORD environment variable.  A sensible default is provided
# for development and testing.
ODDS_PASSWORD = os.environ.get("ODDS_PASSWORD", "odds123")

# Location of the results file.  This JSON file stores completed match
# results across all configured leagues.  Each entry contains
# date, league, homeTeam, awayTeam, homeScore, awayScore and eventId.
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")

# Location of the fixtures file.  This JSON file contains a list of
# upcoming matches (not yet played) used to generate BTTS predictions.
# Each entry includes keys: eventId, league, homeTeam and awayTeam.
FIXTURES_FILE = os.path.join(os.path.dirname(__file__), "fixtures.json")

# Names of the participants used throughout the application.  The order
# determines how assignments are stored and displayed on the front-end.
FRIEND_NAMES: List[str] = [
    "Kenz",
    "Tartz",
    "Coypoo",
    "Ginger",
    "Kooks",
    "Doxy",
]

# Location of the assignments file.  This JSON file will store a
# dictionary mapping each friend name to an event ID (string) or null
# if no assignment has been made.  The file is created on demand.
ASSIGNMENTS_FILE = os.path.join(os.path.dirname(__file__), "assignments.json")

# Location of the group assignments file.  This JSON file will store a
# mapping of each friend to either "top" or "bottom" to determine
# whether they participate in the top bet or the bottom bet.  If the
# file does not exist, a default split (first half top, second half
# bottom) is applied.
GROUPS_FILE      = os.path.join(os.path.dirname(__file__), "groups.json")
NEXT_GROUPS_FILE = os.path.join(os.path.dirname(__file__), "next_groups.json")
SEASON_POINTS_FILE = os.path.join(os.path.dirname(__file__), "season_points.json")
SEASON_STATS_FILE  = os.path.join(os.path.dirname(__file__), "season_stats.json")
GAME_HISTORY_FILE  = os.path.join(os.path.dirname(__file__), "game_history.json")

# Location of the site settings file.  This JSON file stores global
# settings such as the site title and the "any other business" message.
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

# List of ESPN league codes for UK competitions.  These correspond to
# the top four tiers of English football and the top four Scottish
# divisions.  Additional codes can be added here as needed (e.g.
# domestic cups or other European leagues) but are intentionally
# limited to avoid cluttering the match list with too many fixtures.
LEAGUE_CODES: List[str] = [
    # English leagues
    "eng.1",  # Premier League
    "eng.2",  # Championship
    "eng.3",  # League One
    "eng.4",  # League Two
    "eng.5",  # National League
    "eng.6",  # National League North
    "eng.7",  # National League South
    # Scottish leagues
    "sco.1",  # Scottish Premiership
    "sco.2",  # Scottish Championship
    "sco.3",  # Scottish League One
    "sco.4",  # Scottish League Two
    # Welsh league
    "wal.1",  # Cymru Premier
    # Domestic cups
    "eng.fa",         # FA Cup
    "eng.faq",        # FA Cup Qualifying
    "eng.league_cup", # EFL Cup / Carabao Cup
    "eng.charity",    # FA Community Shield
    "eng.trophy",     # EFL Trophy
    "sco.tennents",   # Scottish Cup
    "sco.cis",        # Scottish League Cup
    "sco.challenge",  # Scottish Challenge Cup
    # European competitions
    "uefa.champions",        # UEFA Champions League
    "uefa.champions_qual",   # Champions League Qualifying
    "uefa.europa",           # UEFA Europa League
    "uefa.europa_qual",      # Europa League Qualifying
    "uefa.europa.conf",      # UEFA Conference League
    "uefa.europa.conf_qual", # Conference League Qualifying
    "uefa.super_cup",        # UEFA Super Cup
]

# ── Upcoming matches cache ─────────────────────────────────────────────────────
# Caches the expensive 7-day ESPN fetch for 5 minutes so page loads are instant.
import time as _time
_upcoming_cache: dict = {"data": None, "ts": 0.0}
_UPCOMING_TTL: float = 300.0  # seconds
# ──────────────────────────────────────────────────────────────────────────────


# -----------------------------
# Settings Loading and Saving
# -----------------------------

def load_settings() -> Dict[str, str]:
    """Load global settings from disk.

    In addition to the title and message shown on the main page,
    this function also loads Telegram notification settings.  Keys
    include:

        - title:  site title
        - message:  site-wide message banner
        - telegram_enabled: bool indicating whether Telegram alerts are sent
        - telegram_bot_token: API token for the Telegram bot
        - telegram_chat_id: chat/channel ID where notifications are sent
        - poll_seconds: interval between poll cycles in seconds

    If the settings file does not exist or is malformed, sensible
    defaults are returned.  These defaults come from DEFAULT_TELEGRAM
    and fall back to environment variables where appropriate.
    """
    defaults = {
        "title": "BTTS Match Tracker",
        "message": "",
        "telegram_enabled": DEFAULT_TELEGRAM.get("telegram_enabled", True),
        "telegram_bot_token": DEFAULT_TELEGRAM.get("telegram_bot_token", ""),
        "telegram_chat_id": DEFAULT_TELEGRAM.get("telegram_chat_id", ""),
        "poll_seconds": DEFAULT_TELEGRAM.get("poll_seconds", 30),
        "wa_enabled": False,
    }
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    merged = defaults.copy()
    for key, value in data.items():
        if value not in (None, ""):
            merged[key] = value
    return merged


# -----------------------------
# Results Database
# -----------------------------

def load_results() -> List[dict]:
    """Load historical match results from disk.

    Returns a list of dictionaries, each representing a finished match.
    The file is created on demand if it does not exist or is invalid.
    """
    try:
        with open(RESULTS_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def load_fixtures() -> List[dict]:
    """Load upcoming match fixtures from disk.

    The fixtures file is expected to contain a JSON array of
    dictionaries, each with keys: eventId, league, homeTeam and
    awayTeam.  The file is created by the developer and is not
    automatically updated by the application.  If the file does not
    exist or is malformed, an empty list is returned.

    Returns:
        A list of upcoming match dictionaries.
    """
    try:
        with open(FIXTURES_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_results(results: List[dict]) -> None:
    """Persist the list of match results to disk."""
    try:
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f)
    except Exception:
        # Log failures silently; the caller can handle errors
        pass


def update_results(days_back: int = 7) -> None:
    """Update the results database with completed matches from recent days.

    This function iterates backwards in time for ``days_back`` days and
    fetches scoreboards for each configured league.  For each event
    that has finished (state != "pre"), the final scores are recorded
    into the results database.  Events already present in the database
    (matched by event ID) are skipped to avoid duplicate entries.

    Args:
        days_back: How many days in the past to check.  Defaults to 7.
    """
    results = load_results()
    existing_ids = {str(item.get("eventId")) for item in results if item.get("eventId")}
    tz = pytz.timezone("Europe/London")
    today = datetime.datetime.now(tz)
    # Iterate over each day in the past
    for delta in range(1, days_back + 1):
        date = today - datetime.timedelta(days=delta)
        date_str = date.strftime("%Y%m%d")
        for league in LEAGUE_CODES:
            scoreboard = fetch_scoreboard(league, date_str)
            if not scoreboard:
                continue
            for event in scoreboard.get("events", []):
                event_id = str(event.get("id"))
                # Skip if we've already stored this event
                if event_id in existing_ids:
                    continue
                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                comp = competitions[0]
                competitors = comp.get("competitors", [])
                if len(competitors) != 2:
                    continue
                home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
                if not home_comp or not away_comp:
                    home_comp, away_comp = competitors[0], competitors[1]
                home_score = int(home_comp.get("score", 0)) if home_comp.get("score") else 0
                away_score = int(away_comp.get("score", 0)) if away_comp.get("score") else 0
                # Determine if the match has been played.  Skip scheduled/pre matches.
                state = event.get("status", {}).get("type", {}).get("state", "")
                if state == "pre":
                    continue
                results.append({
                    "eventId": event_id,
                    "date": date_str,
                    "league": league,
                    "homeTeam": home_comp.get("team", {}).get("displayName", ""),
                    "awayTeam": away_comp.get("team", {}).get("displayName", ""),
                    "homeScore": home_score,
                    "awayScore": away_score,
                })
                existing_ids.add(event_id)
    save_results(results)


def compute_btts_predictions(results: List[dict], upcoming_events: List[dict]) -> List[dict]:
    """Compute predicted probabilities for both teams to score for upcoming matches.

    The probability for a match is estimated by multiplying the home team's
    proportion of home games in which they have scored by the away team's
    proportion of away games in which they have scored.  If no historical
    data exists for a team (e.g. new team or no matching records), a
    default probability of 0.5 is used for that team.

    Args:
        results: List of historical match results.
        upcoming_events: List of upcoming events as returned by
            :func:`parse_events_from_scoreboard`.

    Returns:
        A list of dictionaries with keys: eventId, league, homeTeam,
        awayTeam and probability, sorted descending by probability.
    """
    # Build per-team statistics for scoring at home/away
    team_stats: Dict[str, Dict[str, int]] = {}
    for r in results:
        home = r.get("homeTeam") or ""
        away = r.get("awayTeam") or ""
        # Initialise stats entries
        team_stats.setdefault(home, {"home_games": 0, "home_scored": 0, "away_games": 0, "away_scored": 0})
        team_stats.setdefault(away, {"home_games": 0, "home_scored": 0, "away_games": 0, "away_scored": 0})
        # Update home team stats
        team_stats[home]["home_games"] += 1
        if r.get("homeScore", 0) and int(r["homeScore"]) > 0:
            team_stats[home]["home_scored"] += 1
        # Update away team stats
        team_stats[away]["away_games"] += 1
        if r.get("awayScore", 0) and int(r["awayScore"]) > 0:
            team_stats[away]["away_scored"] += 1
    predictions: List[dict] = []
    for event in upcoming_events:
        home = event.get("homeTeam", "")
        away = event.get("awayTeam", "")
        # Home scoring probability
        h_stats = team_stats.get(home)
        if h_stats and h_stats["home_games"] > 0:
            p_home = h_stats["home_scored"] / float(h_stats["home_games"])
        else:
            p_home = 0.5
        # Away scoring probability
        a_stats = team_stats.get(away)
        if a_stats and a_stats["away_games"] > 0:
            p_away = a_stats["away_scored"] / float(a_stats["away_games"])
        else:
            p_away = 0.5
        prob = p_home * p_away
        predictions.append({
            "eventId": event.get("eventId"),
            "league": event.get("league"),
            "homeTeam": home,
            "awayTeam": away,
            "probability": prob,
        })
    # Sort descending by probability
    predictions.sort(key=lambda x: x.get("probability", 0), reverse=True)
    return predictions


def save_settings(settings: Dict[str, str]) -> None:
    """Persist global settings to disk.

    In addition to the title and message, this function persists
    Telegram configuration.  Only recognised keys are saved; other
    keys are ignored to avoid storing unexpected data.  Missing keys
    will revert to defaults on the next load.
    """
    allowed_keys = {
        "title",
        "message",
        "telegram_enabled",
        "telegram_bot_token",
        "telegram_chat_id",
        "poll_seconds",
        "wa_enabled",
    }
    to_save: Dict[str, str] = {}
    for key in allowed_keys:
        val = settings.get(key)
        if val not in (None, ""):
            to_save[key] = val
    with open(SETTINGS_FILE, "w") as f:
        json.dump(to_save, f)

# In-memory cache mapping event IDs to their corresponding league code.
# This allows the API to look up the correct league when retrieving
# detailed information for a specific match.
event_league_map: Dict[str, str] = {}

# ---------------------------------------------------------------------------
# Sofascore fallback map — for matches not covered by ESPN (e.g. sco.3).
# Maps our internal "event ID" (prefixed "sf-") to the Sofascore event ID.
# Populated dynamically when Sofascore matches are added via admin or
# direct assignment.
# ---------------------------------------------------------------------------
SOFASCORE_ID_PREFIX = "sf-"
sofascore_id_map: Dict[str, str] = {}   # our_id -> sofascore_event_id


def _fetch_sofascore_match(sf_id: str) -> Optional[dict]:
    """Fetch live match data from Sofascore and return a normalised dict
    matching the shape returned by api_match, or None on failure."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(
            f"https://api.sofascore.com/api/v1/event/{sf_id}",
            headers=headers, timeout=10
        )
        d = resp.json()
        e = d.get("event", {})
        home_team = e.get("homeTeam", {}).get("name", "")
        away_team = e.get("awayTeam", {}).get("name", "")
        home_score = e.get("homeScore", {}).get("current") or 0
        away_score = e.get("awayScore", {}).get("current") or 0
        status_obj = e.get("status", {})
        sf_status = status_obj.get("type", "notstarted")
        sf_desc = status_obj.get("description", "")
        # Map Sofascore status to ESPN-style state
        if sf_status in ("finished", "afterextratime", "afterpenalties"):
            state = "post"
            status_detail = "FT"
        elif sf_status in ("inprogress", "halftime", "pause"):
            state = "in"
            time_obj = e.get("time", {})
            added = time_obj.get("periodAddedTime", 0)
            if sf_status == "halftime":
                status_detail = "HT"
            else:
                # Calculate elapsed minutes from period start timestamp
                period_start = time_obj.get("currentPeriodStartTimestamp", 0)
                initial = time_obj.get("initial", 0)  # seconds already elapsed at period start
                import time as _time_mod
                if period_start:
                    elapsed = int(((_time_mod.time() - period_start) + initial) / 60)
                    elapsed = max(1, min(elapsed, 90))
                else:
                    elapsed = time_obj.get("played", 0)
                if added:
                    status_detail = f"90+{added}'"
                else:
                    status_detail = f"{elapsed}'"
        else:
            state = "pre"
            import datetime as _dt
            ts = e.get("startTimestamp", 0)
            if ts:
                tz_l = pytz.timezone("Europe/London")
                dt_local = _dt.datetime.fromtimestamp(ts, tz=tz_l)
                status_detail = dt_local.strftime("%A %H:%M")
            else:
                status_detail = sf_desc or "Scheduled"
        hs = int(home_score)
        as_ = int(away_score)
        btts = hs > 0 and as_ > 0
        # calculate_points recalculates scores from key_events (unavailable on Sofascore)
        # so we compute basic scoring directly here instead.
        total = hs + as_
        if hs == 0 and as_ == 0:
            base, base_rule = -1, "Double Doughnut, -1 pt"
        elif (hs >= 5 and as_ == 0) or (as_ >= 5 and hs == 0):
            base, base_rule = -2, f"Super Butler! {max(hs,as_)}-0: one-sided pumping, -2 pts"
        elif hs == 3 and as_ == 3:
            base, base_rule = -3, "Exact 3-3: six goals and the UGSS punishes you, -3 pts"
        elif total >= 5 and btts:
            base, base_rule = 5, f"Goal fest! {total} goals: UGSS maximum, +5 pts"
        elif btts:
            base, base_rule = 2, "Both teams scored: BTTS, +2 pts"
        elif total > 0:
            base, base_rule = 1, f"One team scored: +1 pt"
        else:
            base, base_rule = 0, ""
        scoring = {
            "points": base,
            "baseScore": base,
            "baseRule": base_rule,
            "modifiers": [],
            "btts90plus": False,
            "isDoughnut": (hs == 0 and as_ == 0 and state in ("in", "post")),
            "score90h": hs,
            "score90a": as_,
        }
        ts = e.get("startTimestamp", 0)
        sort_date = ""
        kickoff_time = ""
        try:
            import datetime as _dt
            tz_l = pytz.timezone("Europe/London")
            dt_local = _dt.datetime.fromtimestamp(ts, tz=tz_l)
            sort_date = _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc).isoformat()
            kickoff_time = dt_local.strftime("%H:%M")
        except Exception:
            pass
        return {
            "eventId": f"{SOFASCORE_ID_PREFIX}{sf_id}",
            "league": "sofascore",
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homeScore": int(home_score),
            "awayScore": int(away_score),
            "homeRedCards": 0,
            "awayRedCards": 0,
            "status": status_detail,
            "kickoffTime": kickoff_time,
            "state": state,
            "btts": btts,
            "points": scoring["points"],
            "baseScore": scoring["baseScore"],
            "baseRule": scoring["baseRule"],
            "modifiers": scoring["modifiers"],
            "btts90plus": scoring["btts90plus"],
            "isDoughnut": scoring["isDoughnut"],
            "score90h": scoring["score90h"],
            "score90a": scoring["score90a"],
            "hasET": False,
            "sortDate": sort_date,
        }
    except Exception:
        return None


def get_today_date_str(timezone: str = "Europe/London") -> str:
    """Return today's date in the given timezone formatted as YYYYMMDD.

    The ESPN API uses dates without dashes (YYYYMMDD).  A timezone is
    supplied because the API expects the date relative to local time in
    the user's locale (Europe/London for this project).
    """
    tz = pytz.timezone(timezone)
    now = datetime.datetime.now(tz)
    return now.strftime("%Y%m%d")


def load_assignments() -> Dict[str, Optional[str]]:
    """Load the current match assignments from the JSON file.

    Returns a dictionary mapping each friend name to an event ID (string)
    or None if no assignment has been made.  If the file does not exist
    or is invalid, a fresh mapping with all values set to None is
    returned.  Additional names not present in FRIEND_NAMES are ignored.
    """
    try:
        with open(ASSIGNMENTS_FILE, "r") as f:
            data = json.load(f)
        # Ensure that we only include the expected names
        assignments = {name: data.get(name) for name in FRIEND_NAMES}
    except Exception:
        assignments = {name: None for name in FRIEND_NAMES}
    return assignments


def save_assignments(assignments: Dict[str, Optional[str]]) -> None:
    """Persist the assignments to the JSON file.

    The function writes the provided mapping to disk.  Only keys
    corresponding to FRIEND_NAMES are stored.  Other keys are ignored.
    """
    data = {name: assignments.get(name) for name in FRIEND_NAMES}
    with open(ASSIGNMENTS_FILE, "w") as f:
        json.dump(data, f)


def load_groups() -> Dict[str, str]:
    """Load the current group assignments from the JSON file.

    Returns a dictionary mapping each friend name to either "top" or
    "bottom".  If the file does not exist or is invalid, a default
    assignment is generated where the first half of FRIEND_NAMES are
    "top" and the remainder are "bottom".
    """
    try:
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)
        # Only include expected names and valid values
        groups: Dict[str, str] = {}
        half = len(FRIEND_NAMES) // 2
        for idx, name in enumerate(FRIEND_NAMES):
            val = None
            if isinstance(data, dict):
                val = data.get(name)
            # Accept "sixer" in addition to "top" and "bottom".  If the value
            # from the file is not one of these, fall back to the default top/bottom
            # split based on position.
            if val in {"top", "bottom", "sixer"}:
                groups[name] = val
            else:
                groups[name] = "top" if idx < half else "bottom"
    except Exception:
        # Default assignment: split friends evenly into top and bottom
        groups = {}
        half = len(FRIEND_NAMES) // 2
        for idx, name in enumerate(FRIEND_NAMES):
            groups[name] = "top" if idx < half else "bottom"
    return groups


def save_groups(groups: Dict[str, str]) -> None:
    """Persist the group assignments to the JSON file.

    Only keys corresponding to FRIEND_NAMES are stored.  Unexpected
    values are ignored.  The stored values are "top" or "bottom".
    """
    data: Dict[str, str] = {}
    for name in FRIEND_NAMES:
        val = groups.get(name)
        # Accept "sixer" in addition to "top" and "bottom" when persisting
        # group assignments.  Any other values are ignored.
        if val in {"top", "bottom", "sixer"}:
            data[name] = val
    with open(GROUPS_FILE, "w") as f:
        json.dump(data, f)


def fetch_scoreboard(league: str, date: str) -> Optional[dict]:
    """Fetch the scoreboard for a specific league and date from ESPN.

    Returns a dictionary containing the parsed JSON on success, or
    None if the request fails.  ESPN's API sometimes returns a 400
    message when there are no events for the requested date, so the
    caller should handle a None return value accordingly.

    Some lower leagues (e.g. sco.3, sco.4) don't respond correctly to
    the ?dates= parameter and return 0 events even when games exist.
    For those we fall back to a dateless request which returns the
    current matchweek fixtures.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
    params = {"dates": date}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception:
        return None
    if not isinstance(data, dict) or "events" not in data:
        return None
    # If dated request returns nothing, retry without date param —
    # some lower-tier leagues only serve current matchweek without a date.
    if len(data.get("events", [])) == 0:
        try:
            resp2 = requests.get(url, timeout=10)
            data2 = resp2.json()
            if isinstance(data2, dict) and len(data2.get("events", [])) > 0:
                return data2
        except Exception:
            pass
    return data


def parse_events_from_scoreboard(data: dict, league: str) -> List[dict]:
    """Parse the events from a scoreboard response into a simplified list.

    Each event dictionary in the returned list contains:
        - eventId: a string representing the event's unique ID
        - league: the league code (e.g. "eng.1")
        - homeTeam: display name of the home team
        - awayTeam: display name of the away team
        - title: a human-friendly match title (e.g. "Arsenal vs Chelsea")
        - status: short description of the match status (e.g. "FT")
    """
    events = []
    for event in data.get("events", []):
        event_id = str(event.get("id"))
        # Each event has a "competitions" list with details about the match
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        comp = competitions[0]
        # The competitors array includes two teams with a "homeAway" property
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue
        home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home_comp or not away_comp:
            # If home/away isn't set, assume first is home
            home_comp, away_comp = competitors[0], competitors[1]
        home_team = home_comp.get("team", {}).get("displayName", "")
        away_team = away_comp.get("team", {}).get("displayName", "")
        status_type = event.get("status", {}).get("type", {})
        # Convert scheduled times into UK local time.  ESPN provides the
        # match start time in the event "date" field as an ISO 8601 UTC
        # timestamp (e.g., "2025-08-08T19:00Z").  When the match is
        # scheduled (state == "pre"), we convert this to Europe/London
        # and format it without the US time zone suffix.  For other
        # states (in‑progress, halftime, final), we retain the detail
        # provided by ESPN (e.g., "FT", "Half Time", etc.).
        status_description = status_type.get("detail", "")
        if status_type.get("state") == "pre":
            # Only convert times for scheduled matches
            event_date_str = event.get("date")
            try:
                # Parse the ISO 8601 date string, which is in UTC
                dt_utc = datetime.datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                # Convert to Europe/London timezone
                tz_london = pytz.timezone("Europe/London")
                dt_local = dt_utc.astimezone(tz_london)
                # Format: Fri, August 8 at 8:00 PM UK (no leading zeros on hour/day)
                day_name = dt_local.strftime("%a")
                month_name = dt_local.strftime("%B")
                day = dt_local.day
                hour_min = dt_local.strftime("%I:%M %p").lstrip("0")
                status_description = f"{day_name}, {month_name} {day} at {hour_min} UK"
            except Exception:
                # Fallback to the original detail on parsing errors
                status_description = status_type.get("detail", "")
        title = f"{home_team} vs {away_team}"
        events.append({
            "eventId": event_id,
            "league": league,
            "homeTeam": home_team,
            "awayTeam": away_team,
            "title": title,
            "status": status_description,
            "sortDate": event.get("date", ""),
        })
        # Update the event->league mapping so summary calls know where to look
        event_league_map[event_id] = league
    return events


@app.route("/")
def index() -> str:
    """Serve the main page for the BTTS tracking app."""
    return render_template("index.html")


@app.route("/api/matches")
def api_matches():
    """Return a JSON list of matches available on the given date.

    Optional query parameters:
        date (str): Override the date used when querying ESPN in YYYYMMDD format.

    The endpoint iterates through all configured league codes and aggregates
    the matches into a single list.  Matches are sorted alphabetically by
    the match title for ease of selection on the frontend.
    """
    date_str = request.args.get("date")
    if date_str is None:
        date_str = get_today_date_str()
    all_events: List[dict] = []
    for league in LEAGUE_CODES:
        scoreboard = fetch_scoreboard(league, date_str)
        if scoreboard:
            events = parse_events_from_scoreboard(scoreboard, league)
            all_events.extend(events)
    # Sort events by title for better user experience
    all_events.sort(key=lambda e: e["title"])
    return jsonify(all_events)



def _count_red_cards_from_summary(data: dict, home_team_id: str, away_team_id: str):
    """
    Best-effort counter for red cards per team from an ESPN soccer summary payload.
    Returns (home_reds, away_reds). If not found, both are 0.
    """
    import re as _re
    try:
        home_reds = 0
        away_reds = 0

        def inc(team_id, n=1):
            nonlocal home_reds, away_reds
            if not team_id:
                return
            if str(team_id) == str(home_team_id):
                home_reds += n
            elif str(team_id) == str(away_team_id):
                away_reds += n

        box = (data or {}).get("boxscore", {})
        teams = box.get("teams", []) if isinstance(box.get("teams", []), list) else []
        if len(teams) >= 2:
            for t in teams:
                tid = str(t.get("team", {}).get("id", ""))
                stats_lists = []
                if isinstance(t.get("statistics"), list):
                    stats_lists.append(t["statistics"])
                if isinstance(t.get("teamStats"), list):
                    stats_lists.append(t["teamStats"])
                for stats in stats_lists:
                    for s in stats:
                        values = [
                            s.get("name",""), s.get("displayName",""), s.get("shortDisplayName",""),
                            s.get("abbreviation",""), s.get("label","")
                        ]
                        joined = " ".join([str(v) for v in values]).lower()
                        if "red card" in joined:
                            v = s.get("value")
                            if v is None:
                                dv = s.get("displayValue")
                                try:
                                    v = int(_re.findall(r"\d+", str(dv))[0]) if dv is not None else 0
                                except Exception:
                                    v = 0
                            try:
                                v = int(v)
                            except Exception:
                                v = 0
                            if str(tid) == str(home_team_id):
                                home_reds += v
                            elif str(tid) == str(away_team_id):
                                away_reds += v

        comm = (data or {}).get("commentary", {})
        possible = []
        if isinstance(comm, dict):
            if isinstance(comm.get("plays"), list): possible.append(comm["plays"])
            if isinstance(comm.get("comments"), list): possible.append(comm["comments"])
        if isinstance((data or {}).get("plays"), list):
            possible.append((data or {}).get("plays"))
        for arr in possible:
            for ev in arr:
                joined = " ".join([str(ev.get(k,"")) for k in ("type","card","text","detail","playType","headline")]).lower()
                if "red card" in joined or "straight red" in joined or "second yellow" in joined:
                    tid = ev.get("teamId") or ev.get("team", {}).get("id") or ev.get("homeAway")
                    if tid in ("home","away"):
                        inc(home_team_id if tid=="home" else away_team_id, 1)
                    else:
                        inc(tid, 1)

        hdr = (data or {}).get("header", {})
        if isinstance(hdr.get("incidents"), list):
            for incd in hdr.get("incidents"):
                desc = " ".join([str(incd.get("text","")), str(incd.get("type",""))]).lower()
                if "red card" in desc:
                    inc(incd.get("team", {}).get("id"))

        home_reds = max(0, int(home_reds))
        away_reds = max(0, int(away_reds))
        return home_reds, away_reds
    except Exception:
        return 0, 0

def fetch_match_summary(event_id: str, league: str) -> Optional[dict]:
    """Retrieve a match summary from ESPN given an event ID and league.

    The function returns the parsed JSON data on success or None on
    failure.  A failure can occur if ESPN returns an error (e.g., the
    event hasn't started yet) or the event belongs to a different
    league.  The caller may try other leagues if this returns None.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary"
    params = {"event": event_id}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception:
        return None
    # A valid response will include a 'header' key
    if not isinstance(data, dict) or "header" not in data:
        return None
    return data



def calculate_points(home_score: int, away_score: int, key_events: list,
                     home_team_id: str, away_team_id: str, state: str) -> dict:
    """Calculate sweepstake points from ESPN keyEvents data.

    Base scores (mutually exclusive, highest matching rule wins):
      0-0                                    -> -1
      Butler (5+ one team, 0 other)          -> -2
      Exact 3-3                              -> -3
      One team scores only                   -> 1
      Both score                             -> 2
      Both score in 1st half                 -> 3
      1-1 with an OG                         -> 4
      1st half BTTS  OR  5+ total goals      -> 5

    Modifiers (stack additively):

      BTTS completed by 90+ min goal         -> +1
      Any one team reaches 2 red cards       -> -2
      Any one team reaches 3 red cards       -> +2 (replaces -2)

    Returns a dict with 'points', 'baseRule', and 'modifiers' list.
    """
    import re as _re

    # ── Parse keyEvents ──────────────────────────────────────────────
    goal_events = []      # {team_id, period, clock_secs, type}
    home_reds = 0
    away_reds = 0

    for ev in (key_events or []):
        etype = ev.get('type', {}).get('type', '')
        team_id = str(ev.get('team', {}).get('id', ''))
        period = ev.get('period', {}).get('number', 0)
        clock_val = ev.get('clock', {}).get('value', 0) or 0

        if etype.startswith('goal') or etype == 'own-goal' or etype == 'penalty---scored':
            goal_events.append({
                'team_id': team_id,
                'period': period,
                'clock_secs': float(clock_val),
                'type': etype,
            })

        elif 'red' in etype.lower() or 'red' in ev.get('type', {}).get('text', '').lower():
            if team_id == home_team_id:
                home_reds += 1
            elif team_id == away_team_id:
                away_reds += 1

    # ── 90-minute score (periods 1 & 2 only — ET goals excluded) ──────
    # ESPN uses period 3/4 for extra time. We only count regular time.
    home_90 = sum(1 for g in goal_events if g['team_id'] == home_team_id and g['period'] <= 2)
    away_90 = sum(1 for g in goal_events if g['team_id'] == away_team_id and g['period'] <= 2)
    # Own goals scored in ET also excluded
    # Use 90-min scores for all base score logic
    score_h = home_90
    score_a = away_90

    # ── Derived flags ─────────────────────────────────────────────────
    total_goals = score_h + score_a
    btts = score_h > 0 and score_a > 0

    # Goals by period per team
    home_1h = sum(1 for g in goal_events if g['team_id'] == home_team_id and g['period'] == 1)
    away_1h = sum(1 for g in goal_events if g['team_id'] == away_team_id and g['period'] == 1)
    btts_1h = home_1h > 0 and away_1h > 0

    # Own goal check for 1-1 OG rule
    has_og = any(g['type'] == 'own-goal' for g in goal_events)

    # Butler: 5+ by one team, 0 by other
    is_butler = (score_h >= 5 and score_a == 0) or (score_a >= 5 and score_h == 0)

    # 90+ min goal that completed BTTS
    # A goal is 90+ if clock_secs >= 5400 (90 * 60) or period > 2
    def is_90plus(g):
        return g['clock_secs'] >= 5400 or g['period'] > 2

    cash_clincher = False
    if btts and state == 'post':
        # Was BTTS completed by a 90+ min goal?
        # Sort goals by clock; find the goal that made both teams have scored
        sorted_goals = sorted(goal_events, key=lambda g: (g['period'], g['clock_secs']))
        home_scored = 0
        away_scored = 0
        for g in sorted_goals:
            if g['team_id'] == home_team_id:
                home_scored += 1
            elif g['team_id'] == away_team_id:
                away_scored += 1
            # This goal just completed BTTS
            if home_scored > 0 and away_scored > 0:
                if is_90plus(g):
                    cash_clincher = True
                break

    # ── Base score ────────────────────────────────────────────────────
    base = 0
    base_rule = 'No score yet'

    if state in ('in', 'post') or total_goals > 0:
        live = (state == 'in')
        if score_h == 0 and score_a == 0:
            base = -1
            base_rule = 'Double Doughnut incoming, -1 pt' if live else 'Double Doughnut, -1 pt'
        elif is_butler:
            base = -2
            top = score_h if score_h >= 5 else score_a
            base_rule = f'Super Butler! {top}-0: one-sided pumping, -2 pts'
        elif score_h == 3 and score_a == 3:
            base = -3
            base_rule = 'Exact 3-3: six goals and the UGSS is punishing you, -3 pts' if live else 'Exact 3-3: six goals and the UGSS punishes you, -3 pts'
        elif total_goals >= 5:
            base = 5
            if btts_1h:
                base_rule = f'Goal fest! {total_goals} goals, both scored in 1st half: UGSS maximum, +5 pts'
            else:
                base_rule = f'Goal fest! {total_goals} goals: UGSS maximum, +5 pts'
        elif btts_1h:
            base = 3
            base_rule = f'Both scored in 1st half: beating standard BTTS, +3 pts' if live else f'Both scored in 1st half: beats standard BTTS, +3 pts'
        elif score_h == 1 and score_a == 1 and has_og:
            base = 4
            base_rule = 'Rare UGSS bonus: 1-1 with an Own Goal, +4 pts'
        elif btts:
            base = 2
            base_rule = 'Both teams scoring: BTTS on, +2 pts' if live else 'Both teams scored: BTTS, +2 pts'
        elif score_h > 0 or score_a > 0:
            base = 1
            _butler = min(score_h, score_a) == 0
            _label = f'Butler ({max(score_h,score_a)}-0)' if _butler else 'One team scored'
            if state == 'post':
                base_rule = f'{_label}: one team scored, +1 pt'
            else:
                base_rule = f'{_label}: +1 pt for now, still waiting for BTTS'

    # ── Modifiers ─────────────────────────────────────────────────────
    modifiers = []
    modifier_total = 0

    # Note: cash_clincher (+1) and social penalty (-1) are applied by the frontend once it confirms
    # the other games in the same group also have BTTS. We just flag here.

    # Red card modifiers — triggers once if AT LEAST one team hits the threshold
    max_reds = max(home_reds, away_reds)
    if max_reds >= 3:
        modifiers.append(('3 reds for one team — chaos bonus', +2))
        modifier_total += 2
    elif max_reds >= 2:
        modifiers.append(('2 reds for one team', -2))
        modifier_total -= 2

    total = base + modifier_total
    is_doughnut = (score_h == 0 and score_a == 0 and state in ('in', 'post'))
    # Detect if game went to extra time (goals in period 3 or 4)
    has_et = any(g['period'] > 2 for g in goal_events)
    return {
        'points': total,
        'baseScore': base,
        'baseRule': base_rule,
        'modifiers': modifiers,
        'btts90plus': cash_clincher,
        'isDoughnut': is_doughnut,
        'score90h': score_h,
        'score90a': score_a,
        'hasET': has_et,
    }


@app.route("/api/match/<event_id>")
def api_match(event_id: str):
    """Return detailed information about a specific match.

    The endpoint attempts to locate the league associated with the
    provided event ID using the in-memory event_league_map.  If the
    mapping isn't present (for instance, when the server has just
    started), it iterates through all configured leagues until it
    retrieves a successful summary.  This may incur additional
    requests on first call but ensures resilience.

    Event IDs prefixed with "sf-" are fetched from Sofascore instead
    of ESPN, allowing coverage of leagues not indexed by ESPN.
    """
    # Sofascore fallback for leagues not covered by ESPN
    if event_id.startswith(SOFASCORE_ID_PREFIX):
        sf_id = event_id[len(SOFASCORE_ID_PREFIX):]
        result = _fetch_sofascore_match(sf_id)
        if result:
            return jsonify(result)
        return jsonify({"error": "Sofascore match not found"}), 404

    # Determine which league to query
    league = event_league_map.get(event_id)
    data = None
    leagues_to_try = [league] if league else LEAGUE_CODES
    for lg in leagues_to_try:
        if lg is None:
            continue
        summary = fetch_match_summary(event_id, lg)
        if summary:
            data = summary
            league = lg
            # Update mapping for faster lookups next time
            event_league_map[event_id] = lg
            break
    if not data:
        return jsonify({"error": "Match not found"}), 404
    header = data.get("header", {})
    competitions = header.get("competitions", [])
    if not competitions:
        return jsonify({"error": "Match data unavailable"}), 500
    comp = competitions[0]
    competitors = comp.get("competitors", [])
    # Determine home and away and their scores
    home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if not home_comp or not away_comp:
        home_comp, away_comp = competitors[0], competitors[1]
    home_team = home_comp.get("team", {}).get("displayName", "")
    away_team = away_comp.get("team", {}).get("displayName", "")
    home_score = int(home_comp.get("score", 0)) if home_comp.get("score") else 0
    away_score = int(away_comp.get("score", 0)) if away_comp.get("score") else 0
    # Status information
    comp_status = header.get("competitions", [{}])[0].get("status", {})
    status_type = comp_status.get("type", {})
    state = status_type.get("state", "")
    status_detail = status_type.get("detail", "")
    # Convert the ESPN event date (UTC) to UK local time and compute kickoff details.
    # For scheduled matches (state == "pre"), we display the day of the week and 24‑hour
    # time (e.g. "Saturday 15:00").  For in‑progress or finished matches, kickoff_time is
    # still provided but the status from ESPN is used for minutes/HT/FT.  We avoid
    # including the full date because the matches we track are within a few days.
    event_date_str = header.get("competitions", [{}])[0].get("date")
    kickoff_time = ""
    try:
        dt_utc = datetime.datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
        tz_london = pytz.timezone("Europe/London")
        dt_local = dt_utc.astimezone(tz_london)
        # Default kickoff time: 24‑hour HH:MM for non‑scheduled contexts
        kickoff_time = dt_local.strftime("%H:%M")
        if state == "pre":
            # For scheduled games, include the day of week and 24‑hour time (e.g. Saturday 15:00)
            kickoff_time = dt_local.strftime("%A %H:%M")
            # Ensure status_detail is simply "Scheduled" or whatever ESPN provides; we leave
            # the status_detail unchanged here because the front‑end uses kickoff_time.
    except Exception:
        kickoff_time = ""
    # Determine if both teams have scored (BTTS)
    btts = home_score > 0 and away_score > 0
    try:
        home_id = str(home_comp.get('team', {}).get('id', ''))
        away_id = str(away_comp.get('team', {}).get('id', ''))
    except Exception:
        home_id = ''
        away_id = ''
    home_red, away_red = _count_red_cards_from_summary(data, home_id, away_id)

    # Calculate sweepstake points from keyEvents
    key_events = data.get("keyEvents", [])
    scoring = calculate_points(home_score, away_score, key_events, home_id, away_id, state)

    return jsonify({
        "eventId": event_id,
        "league": league,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "homeScore": home_score,
        "awayScore": away_score,
        "homeRedCards": int(home_red), "awayRedCards": int(away_red),
        "status": status_detail,
        "kickoffTime": kickoff_time,
        "state": state,
        "btts": btts,
        "points": scoring["points"],
        "baseScore": scoring["baseScore"],
        "baseRule": scoring["baseRule"],
        "modifiers": scoring["modifiers"],
        "btts90plus": scoring["btts90plus"],
        "isDoughnut": scoring["isDoughnut"],
        "score90h": scoring["score90h"],
        "score90a": scoring["score90a"],
        "hasET": scoring["hasET"],
        "sortDate": event_date_str or "",
    })


# -----------------------------
# Authentication and Admin API
# -----------------------------


def load_season_points() -> Dict[str, Any]:
    """Load carry-forward season points from disk."""
    try:
        with open(SEASON_POINTS_FILE, "r") as f:
            data = json.load(f)
        result = {name: int(data.get(name, 0)) for name in FRIEND_NAMES}
        result['_lastUpdated'] = data.get('_lastUpdated', '')
        return result
    except Exception:
        return {name: 0 for name in FRIEND_NAMES}


def save_season_points(points: Dict[str, Any]) -> None:
    """Save carry-forward season points to disk."""
    with open(SEASON_POINTS_FILE, "w") as f:
        json.dump(points, f, indent=2)


@app.route("/api/season_points", methods=["GET", "POST"])
def api_season_points():
    """Get or update carry-forward season points."""
    if request.method == "GET":
        return jsonify(load_season_points())
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    points = load_season_points()
    for name in FRIEND_NAMES:
        if name in data:
            try:
                points[name] = int(data[name])
            except (ValueError, TypeError):
                pass
    # Stamp with today's date
    import datetime as _dt
    points['_lastUpdated'] = _dt.date.today().strftime('%d %b %Y')
    save_season_points(points)
    return jsonify({"success": True})

@app.route("/api/login", methods=["POST"])
def api_login():
    """Authenticate the admin user using a password.

    Expects JSON with a "password" field.  If the password matches
    ADMIN_PASSWORD, a session flag is set and a success response is
    returned.  Otherwise, a 401 Unauthorized response is sent.
    """
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    if password and password == ADMIN_PASSWORD:
        session["admin"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid password"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    """Log out the current admin session."""
    session.pop("admin", None)
    return jsonify({"success": True})


@app.route("/api/assignments", methods=["GET", "POST"])
def api_assignments():
    """Get or update match assignments for each friend.

    GET: returns a JSON object mapping friend names to event IDs or
    null if not assigned.

    POST: expects JSON with friend names as keys and event IDs as
    values (or null to clear).  Requires an admin session; if not
    authenticated, returns 401.  The assignments are saved to disk.
    """
    if request.method == "GET":
        return jsonify(load_assignments())
    # POST requires admin session
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    assignments = load_assignments()
    for name in FRIEND_NAMES:
        # Accept empty string or None to clear the assignment
        value = data.get(name)
        assignments[name] = value if value else None
    save_assignments(assignments)
    return jsonify({"success": True})


@app.route("/api/next_groups", methods=["GET"])
def api_next_groups():
    """Return projected groups for the next round based on current standings."""
    try:
        with open(NEXT_GROUPS_FILE, "r") as f:
            return jsonify(json.load(f))
    except Exception:
        # Fall back to current groups if next_groups doesn't exist yet
        return jsonify(load_groups())


@app.route("/api/groups", methods=["GET", "POST"])
def api_groups():
    """Get or update the friend group assignments (top/bottom).

    GET: returns a JSON object mapping friend names to either "top" or
    "bottom".

    POST: expects JSON with friend names as keys and values of
    "top" or "bottom".  Requires an admin session.  Invalid values
    are ignored.  After saving, returns a success flag.
    """
    if request.method == "GET":
        return jsonify(load_groups())
    # POST requires admin session
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    groups = load_groups()
    updated: Dict[str, str] = {}
    for name in FRIEND_NAMES:
        val = data.get(name)
        # Accept "sixer" in addition to "top" and "bottom"
        if val in {"top", "bottom", "sixer"}:
            updated[name] = val
        else:
            # Preserve existing assignment if not provided
            updated[name] = groups.get(name, "top")
    save_groups(updated)
    return jsonify({"success": True})


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """Get or update global site settings.

    GET: returns the current settings dictionary with keys 'title' and 'message'.
    POST: expects JSON with optional 'title' and 'message' fields.  Requires
    an admin session.  Missing values are treated as empty strings (or
    default for title).  On success, a success flag is returned.
    """
    if request.method == "GET":
        return jsonify(load_settings())
    # POST requires admin session
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title") or "BTTS Match Tracker"
    message = data.get("message") or ""
    save_settings({"title": title, "message": message})
    return jsonify({"success": True})


@app.route("/api/search_matches")
def api_search_matches():
    """Search for matches across leagues in a given date range.

    Query parameters:
        start (str): start date in YYYYMMDD or YYYY-MM-DD format.  Defaults to today.
        end   (str): end date in YYYYMMDD or YYYY-MM-DD format.  Defaults to start.

    The endpoint iterates through all configured league codes and
    aggregates matches within the range.  Results are sorted
    alphabetically by match title.  Scheduled times are converted to
    UK local time.
    """
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if not start_str:
        start_str = get_today_date_str()
    if not end_str:
        end_str = start_str
    # Remove any hyphens to match ESPN date formatting
    start_clean = start_str.replace("-", "")
    end_clean = end_str.replace("-", "")
    # Compose the dates parameter.  ESPN supports ranges like
    # yyyyMMdd-yyyyMMdd for multiple days【812553852205208†L331-L343】.
    dates_param = start_clean if start_clean == end_clean else f"{start_clean}-{end_clean}"
    all_events: List[dict] = []
    for league in LEAGUE_CODES:
        scoreboard = fetch_scoreboard(league, dates_param)
        if scoreboard:
            events = parse_events_from_scoreboard(scoreboard, league)
            all_events.extend(events)
    # Remove duplicates (rare but possible when a match appears in multiple leagues) by eventId
    unique_events: Dict[str, dict] = {}
    for event in all_events:
        unique_events[event["eventId"]] = event
    # Convert to list and sort by title
    sorted_events = sorted(unique_events.values(), key=lambda e: (e.get("sortDate",""), e["title"]))
    return jsonify(sorted_events)




@app.route("/api/season_stats", methods=["GET"])
def api_season_stats():
    """Return per-player season stats from disk."""
    try:
        with open(SEASON_STATS_FILE, "r") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({})

@app.route("/api/game_history", methods=["GET"])
def api_game_history():
    """Return the full game history log — every round ever recorded."""
    return jsonify(load_game_history())

@app.route("/leaderboard")
def leaderboard_page() -> str:
    """Serve the public leaderboard page."""
    return render_template("leaderboard.html")

@app.route("/test")
def test_page():
    """Serve the scoring test/simulator page."""
    return render_template("test.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html", app_version=APP_VERSION)


@app.route("/api/admin_status")
def api_admin_status():
    """Return whether the current session is authenticated as admin."""
    return jsonify({"admin": bool(session.get("admin"))})


@app.route("/api/upcoming_matches")
def api_upcoming_matches():
    """Return matches from 3 days ago through 3 days ahead.

    Results are cached for 5 minutes so repeated page loads don't hammer ESPN.
    """
    global _upcoming_cache
    now_ts = _time.monotonic()
    if _upcoming_cache["data"] is not None and (now_ts - _upcoming_cache["ts"]) < _UPCOMING_TTL:
        return jsonify(_upcoming_cache["data"])

    tz = pytz.timezone("Europe/London")
    now = datetime.datetime.now(tz).date()
    start_date = now - datetime.timedelta(days=3)
    end_date   = now + datetime.timedelta(days=3)
    start_str  = start_date.strftime("%Y%m%d")
    end_str    = end_date.strftime("%Y%m%d")
    date_range_param = f"{start_str}-{end_str}"
    all_events: List[dict] = []
    for league in LEAGUE_CODES:
        scoreboard = fetch_scoreboard(league, date_range_param)
        if scoreboard:
            events = parse_events_from_scoreboard(scoreboard, league)
            all_events.extend(events)
    # Deduplicate by eventId and sort by date then title
    unique_events: Dict[str, dict] = {}
    for event in all_events:
        unique_events[event["eventId"]] = event
    sorted_events = sorted(unique_events.values(), key=lambda e: (e.get("sortDate",""), e["title"]))
    _upcoming_cache["data"] = sorted_events
    _upcoming_cache["ts"]   = now_ts
    return jsonify(sorted_events)


# -----------------------------
# Odds Page and Predictions API
# -----------------------------

@app.route("/api/odds_login", methods=["POST"])
def api_odds_login():
    """Authenticate a user for access to the odds page.

    Expects a JSON payload with a 'password' field.  If the password
    matches the configured ODDS_PASSWORD, a session flag is set and a
    success response is returned.  Otherwise, a 401 Unauthorized
    response is sent.
    """
    data = request.get_json(silent=True) or {}
    password = data.get("password")
    if password and password == ODDS_PASSWORD:
        session["odds"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid password"}), 401


@app.route("/api/odds_logout", methods=["POST"])
def api_odds_logout():
    """Log out the current odds session."""
    session.pop("odds", None)
    return jsonify({"success": True})


@app.route("/api/update_results", methods=["POST"])
def api_update_results():
    """Trigger an update of the historical results database.

    Requires a valid odds or admin session.  Accepts an optional
    'days' field in the JSON payload specifying how many days back
    to fetch results.  Defaults to 7 days.  Returns a success flag
    when the update completes.
    """
    if not session.get("odds") and not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        days = int(data.get("days", 7))
    except Exception:
        days = 7
    # Limit the number of days to prevent excessive requests
    days = max(1, min(days, 31))
    update_results(days_back=days)
    return jsonify({"success": True})


@app.route("/api/btts_predictions")
def api_btts_predictions():
    """Return the top BTTS predictions for upcoming matches.

    Requires an odds or admin session.  Accepts an optional 'limit'
    query parameter specifying how many predictions to return.
    The function looks ahead four days (inclusive) from today, loads
    historical results and computes probabilities for upcoming
    fixtures.  Results are sorted by probability in descending
    order and truncated to the requested limit.
    """
    if not session.get("odds") and not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        limit = int(request.args.get("limit", 5))
    except Exception:
        limit = 5
    limit = max(1, min(limit, 20))
    # Retrieve upcoming matches from the fixtures file.  In development
    # environments without network access, we rely on a static list
    # of fixtures rather than calling the ESPN API.  Should the
    # fixtures file be empty, fallback to attempting to fetch from
    # ESPN for completeness.  For local development, this call
    # typically fails due to network restrictions.
    upcoming_events: List[dict] = load_fixtures()
    if not upcoming_events:
        # Fallback: attempt to fetch the next 4 days of fixtures from ESPN
        tz = pytz.timezone("Europe/London")
        now_date = datetime.datetime.now(tz).date()
        end_date = now_date + datetime.timedelta(days=3)
        start_str = now_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        date_range_param = f"{start_str}-{end_str}"
        upcoming: List[dict] = []
        for lg in LEAGUE_CODES:
            scoreboard = fetch_scoreboard(lg, date_range_param)
            if scoreboard:
                events = parse_events_from_scoreboard(scoreboard, lg)
                upcoming.extend(events)
        # Remove duplicates by eventId
        unique_upcoming: Dict[str, dict] = {}
        for ev in upcoming:
            unique_upcoming[ev["eventId"]] = ev
        upcoming_events = list(unique_upcoming.values())
    # Load historical results
    results = load_results()
    predictions = compute_btts_predictions(results, upcoming_events)
    # Select top predictions by probability
    top = predictions[:limit]
    # Round probability to two decimal places for display
    for item in top:
        item["probability"] = round(item["probability"], 2)
    return jsonify(top)


@app.route("/odds")
def odds_page():
    """Serve the odds page, which requires a password."""
    return render_template("odds.html", app_version=APP_VERSION)



# -----------------------------
# Telegram Notifications
# -----------------------------
import threading
import time

DEFAULT_TELEGRAM = {
    "telegram_enabled": True,
    "telegram_bot_token": "8223356225:AAEXDceBKCRYH3LJz7RnAD_O7gjLEtOM8nc",
    "telegram_chat_id": "1419645400",
    "poll_seconds": 30
}

NOTIFY_STATE_FILE = os.path.join(os.path.dirname(__file__), "notify_state.json")
_notifier_started = False

def tg_settings():
    s = load_settings()
    cfg = DEFAULT_TELEGRAM.copy()
    for k in ("telegram_enabled","telegram_bot_token","telegram_chat_id","poll_seconds"):
        if k in s and s[k] not in (None, ""):
            cfg[k] = s[k]
    return cfg

def tg_send_message(text: str) -> bool:
    cfg = tg_settings()
    if not cfg.get("telegram_enabled"): 
        return False
    token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        )
        return resp.ok
    except Exception:
        return False

# Full name mapping for WhatsApp @mentions — must match address book names exactly
WA_FRIEND_NAMES = {
    "Kenz":   "Martin MacKenzie",
    "Tartz":  "Martin Coughlan",
    "Coypoo": "Martin Coyle",
    "Ginger": "Marc McColgan",
    "Kooks":  "Craig Coughlan",
    "Doxy":   "Mark Docherty",
}

def wa_send_message(text: str) -> bool:
    """Send a message to the WhatsApp group via the local WA bridge."""
    cfg = load_settings()
    if not cfg.get("wa_enabled"):
        return False
    jid = os.environ.get("WA_GROUP_JID", "")
    if not jid:
        return False
    try:
        resp = requests.post(
            "http://172.17.0.1:8097/send",
            json={"jid": jid, "message": text},
            timeout=5
        )
        return resp.ok
    except Exception:
        return False

def load_notify_state():
    try:
        with open(NOTIFY_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_notify_state(state):
    try:
        with open(NOTIFY_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def get_match_info_for_event(event_id: str):
    league = event_league_map.get(event_id)
    data = None
    leagues_to_try = [league] if league else LEAGUE_CODES
    for lg in leagues_to_try:
        if lg is None: continue
        summary = fetch_match_summary(event_id, lg)
        if summary:
            data = summary
            league = lg
            event_league_map[event_id] = lg
            break
    if not data:
        for lg in LEAGUE_CODES:
            summary = fetch_match_summary(event_id, lg)
            if summary:
                data = summary; event_league_map[event_id] = lg; league = lg; break
    if not data: return None

    header = data.get("header", {})
    competitions = header.get("competitions", [{}])
    comp = competitions[0] if competitions else {}
    status = comp.get("status", {}).get("type", {}) or {}
    state = status.get("state", "" )
    status_detail = comp.get("status", {}).get("type", {}).get("shortDetail") or comp.get("status", {}).get("type", {}).get("detail") or ""
    competitors = comp.get("competitors", [])
    home_team = away_team = ""
    home_score = away_score = 0
    for c in competitors:
        if c.get("homeAway") == "home":
            home_team = c.get("team", {}).get("name", "")
            try: home_score = int(c.get("score", 0))
            except: home_score = 0
        elif c.get("homeAway") == "away":
            away_team = c.get("team", {}).get("name", "")
            try: away_score = int(c.get("score", 0))
            except: away_score = 0
    event_date_str = comp.get("date") or header.get("competitions", [{}])[0].get("date")
    kickoff_time = ""
    try:
        dt_utc = datetime.datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
        tz_london = pytz.timezone("Europe/London")
        dt_local = dt_utc.astimezone(tz_london)
        kickoff_time = dt_local.strftime("%H:%M")
        if state == "pre":
            kickoff_time = dt_local.strftime("%A %H:%M")
    except Exception:
        kickoff_time = ""
    btts = home_score > 0 and away_score > 0
    try:
        home_id = str(home_comp.get("team", {}).get("id", ""))
        away_id = str(away_comp.get("team", {}).get("id", ""))
    except Exception:
        home_id = ""
        away_id = ""
    home_red, away_red = _count_red_cards_from_summary(data, home_id, away_id)
    return {
        "eventId": event_id,
        "league": league,
        "homeTeam": home_team, "awayTeam": away_team,
        "homeScore": home_score, "awayScore": away_score,
        "homeRedCards": int(home_red), "awayRedCards": int(away_red),
        "status": status_detail, "state": state,
        "kickoffTime": kickoff_time, "btts": btts
    }

def format_minute(status_detail: str):
    if not status_detail: return ""
    return status_detail

def load_game_history() -> list:
    try:
        with open(GAME_HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_game_history(history: list) -> None:
    try:
        with open(GAME_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def _compute_stat_increments(hs: int, as_: int, state: str) -> dict:
    """Return the season_stats fields to increment by 1 for a finished match."""
    increments = {}
    if state != "post":
        return increments
    total = hs + as_
    btts = hs > 0 and as_ > 0
    is_butler = (hs >= 5 and as_ == 0) or (as_ >= 5 and hs == 0)
    is_donut = (hs == 0 and as_ == 0)
    is_33 = (hs == 3 and as_ == 3)
    is_super_butler = is_butler  # 5-0 or more
    # Base outcome
    if is_donut:
        increments["donuts"] = 1
    elif is_super_butler:
        increments["superButlers"] = 1
        increments["butlers"] = 1
    elif is_33:
        increments["threethrees"] = 1
    elif total >= 5 and btts:
        increments["fives"] = 1
        increments["btts"] = 1
    elif btts:
        increments["btts"] = 1
    elif total > 0:
        increments["butlers"] = 1
    return increments


def _auto_update_season_stats(results: dict, round_date: str = "") -> None:
    """Increment season_stats for each player based on their finished match result,
    and append a permanent record to game_history.json.

    results: dict of {player: {hs, as_, state, homeTeam, awayTeam, eventId}}
    """
    try:
        stats = json.load(open(SEASON_STATS_FILE))
        for player, r in results.items():
            if player not in stats:
                continue
            increments = _compute_stat_increments(r["hs"], r["as_"], r["state"])
            for field, val in increments.items():
                stats[player][field] = stats[player].get(field, 0) + val
        with open(SEASON_STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
    except Exception:
        pass  # Never crash the notifier over stats

    # Write permanent game history record
    try:
        history = load_game_history()
        tz_l = pytz.timezone("Europe/London")
        date_str = round_date or datetime.datetime.now(tz_l).strftime("%Y-%m-%d")
        round_entry = {
            "date": date_str,
            "games": {}
        }
        for player, r in results.items():
            hs, as_ = r["hs"], r["as_"]
            total = hs + as_
            btts = hs > 0 and as_ > 0
            is_butler = (hs >= 5 and as_ == 0) or (as_ >= 5 and hs == 0)
            is_donut = (hs == 0 and as_ == 0)
            is_33 = (hs == 3 and as_ == 3)
            if is_donut:
                outcome = "donut"
            elif is_33:
                outcome = "3-3"
            elif is_butler:
                outcome = "superButler"
            elif total >= 5 and btts:
                outcome = "fives"
            elif btts:
                outcome = "btts"
            elif total > 0:
                outcome = "butler"
            else:
                outcome = "unknown"
            round_entry["games"][player] = {
                "eventId": r.get("eventId", ""),
                "homeTeam": r.get("homeTeam", ""),
                "awayTeam": r.get("awayTeam", ""),
                "score": f"{hs}-{as_}",
                "outcome": outcome,
            }
        history.append(round_entry)
        save_game_history(history)
    except Exception:
        pass


def _compute_base_points(hs: int, as_: int) -> int:
    """Return base UGSS points for a finished score (no social modifiers)."""
    total = hs + as_
    btts  = hs > 0 and as_ > 0
    if hs == 0 and as_ == 0:
        return -1
    if (hs >= 5 and as_ == 0) or (as_ >= 5 and hs == 0):
        return -2
    if hs == 3 and as_ == 3:
        return -3
    if total >= 5 and btts:
        return 5
    if btts:
        # 1st-half BTTS can't be derived here without key_events so we cap at +2
        # (cash_clincher likewise needs live data; those are edge cases the admin can correct)
        return 2
    return 1  # one team scored (butler)


def _auto_update_season_points(results: dict) -> None:
    """Recompute and write season_points.json after a round completes.

    Applies:
      - base UGSS points per player from their match score
      - social coster: player had no BTTS, both group-mates did → -1
      - social clincher: player completed BTTS AND both group-mates already had it → +1
        (this requires btts90plus flag from live data; skipped in auto-calc but
         history entries corrected later by admin if needed)

    Does NOT apply in-game red card modifiers (those are computed live only).
    """
    try:
        season = json.load(open(SEASON_POINTS_FILE))
        groups = json.load(open(GROUPS_FILE))

        # Determine BTTS per player
        btts_by_player = {p: (r["hs"] > 0 and r["as_"] > 0) for p, r in results.items()}

        # Group members (top / bottom)
        group_members: dict = {}
        for player, grp in groups.items():
            group_members.setdefault(grp, []).append(player)

        # Compute points per player
        today_pts: dict = {}
        for player, r in results.items():
            base = _compute_base_points(r["hs"], r["as_"])
            grp  = groups.get(player)
            mates = [p for p in group_members.get(grp, []) if p != player]

            my_btts    = btts_by_player.get(player, False)
            mates_btts = all(btts_by_player.get(m, False) for m in mates)

            is_butler = (r["hs"] > 0 or r["as_"] > 0) and not my_btts  # one team scored, other didn't
            coster    = is_butler and mates_btts  # Butler AND both mates had BTTS → Coster
            # 0-0 Double Doughnut does NOT trigger a Coster — both teams cost the money
            clincher  = False  # can't detect 90+ from stored scores; leave for manual

            pts = base
            if coster:
                pts -= 1
            if clincher:
                pts += 1
            today_pts[player] = pts

        # Apply to season totals
        tz_l = pytz.timezone("Europe/London")
        date_str = datetime.datetime.now(tz_l).strftime("%d %b %Y")
        for player, delta in today_pts.items():
            if player in season and not str(player).startswith("_"):
                season[player] = season.get(player, 0) + delta
        season["_lastUpdated"] = date_str

        with open(SEASON_POINTS_FILE, "w") as f:
            json.dump(season, f, indent=2)

    except Exception:
        pass  # Never crash the notifier


def _auto_update_groups() -> None:
    """After a round completes, project next-round groups from current standings
    and write to next_groups.json. Does NOT touch groups.json (the active round groups).
    Sort: points desc → BTTS count desc → alphabetical. Top 3 → 'top', bottom 3 → 'bottom'."""
    try:
        season = json.load(open(SEASON_POINTS_FILE))
        stats  = json.load(open(SEASON_STATS_FILE))
        ranked = sorted(
            [(p, v) for p, v in season.items() if not p.startswith("_")],
            key=lambda x: (-x[1], -(stats.get(x[0], {}).get("btts", 0)), x[0])
        )
        next_groups = {}
        for i, (player, _) in enumerate(ranked):
            next_groups[player] = "top" if i < 3 else "bottom"
        with open(NEXT_GROUPS_FILE, "w") as f:
            json.dump(next_groups, f, indent=2)
    except Exception:
        pass  # Never crash the notifier


def notifier_loop():
    state = load_notify_state()
    while True:
        try:
            cfg = tg_settings()
            if not cfg.get("telegram_enabled"):
                time.sleep(cfg.get("poll_seconds",30)); 
                continue
            assignments = load_assignments()
            match_results = {}  # player -> {hs, as_, state} for auto-stats
            for friend, event_id in assignments.items():
                if not event_id: continue
                # Sofascore fallback
                if event_id.startswith(SOFASCORE_ID_PREFIX):
                    sf_id = event_id[len(SOFASCORE_ID_PREFIX):]
                    info_full = _fetch_sofascore_match(sf_id)
                    if not info_full:
                        continue
                    info = {
                        "eventId": event_id,
                        "homeTeam": info_full["homeTeam"],
                        "awayTeam": info_full["awayTeam"],
                        "homeScore": info_full["homeScore"],
                        "awayScore": info_full["awayScore"],
                        "state": info_full["state"],
                        "status": info_full["status"],
                        "kickoffTime": info_full["kickoffTime"],
                        "btts": info_full["btts"],
                    }
                else:
                    info = get_match_info_for_event(event_id)
                if not info: continue
                key = event_id
                prev = state.get(key, {"state": "", "homeScore": 0, "awayScore": 0, "kickoffSent": False, "bttsSent": False, "ftSent": False})
                cur_state = info["state"]
                hs, as_ = info["homeScore"], info["awayScore"]
                minute = format_minute(info.get("status",""))
                if cur_state == "in" and not prev.get("kickoffSent"):
                    tg_send_message(f"Kickoff {friend}: {info['homeTeam']} vs {info['awayTeam']} ({info['kickoffTime']})")
                    prev["kickoffSent"] = True
                if (hs != prev.get("homeScore") or as_ != prev.get("awayScore")) and cur_state == "in":
                    tg_send_message(f"Goal for {friend}: {info['homeTeam']} {hs} {info['awayTeam']} {as_} - {minute}")
                    wa_send_message(f"⚽️ @{WA_FRIEND_NAMES.get(friend, friend)}")
                if info["btts"] and not prev.get("bttsSent"):
                    tg_send_message(f"BTTS {friend}: Both teams have scored - {info['homeTeam']} {hs} {info['awayTeam']} {as_} ({minute})")
                    wa_send_message(f"✅ @{WA_FRIEND_NAMES.get(friend, friend)}")
                    prev["bttsSent"] = True
                if cur_state == "post" and not prev.get("ftSent"):
                    tg_send_message(f"FT {friend}: {info['homeTeam']} {hs} {info['awayTeam']} {as_}")
                    prev["ftSent"] = True
                prev["state"] = cur_state
                prev["homeScore"] = hs
                prev["awayScore"] = as_
                state[key] = prev
                match_results[friend] = {
                    "hs": hs, "as_": as_, "state": cur_state,
                    "homeTeam": info.get("homeTeam", ""),
                    "awayTeam": info.get("awayTeam", ""),
                    "eventId": event_id,
                }

            # Auto-update season stats + points once ALL assigned games are finished
            if assignments and all(v.get("state") == "post" for v in match_results.values()):
                stats_key = "statsUpdated_" + "_".join(sorted(assignments.values()))
                if not state.get(stats_key):
                    _auto_update_season_stats(match_results)
                    _auto_update_season_points(match_results)
                    _auto_update_groups()
                    state[stats_key] = True
                    # Build summary for Telegram
                    try:
                        sp = json.load(open(SEASON_POINTS_FILE))
                        stats_snap = json.load(open(SEASON_STATS_FILE))
                        ranked = sorted(
                            [(p, sp[p]) for p in sp if not p.startswith("_")],
                            key=lambda x: (-x[1], -(stats_snap.get(x[0], {}).get("btts", 0)), x[0])
                        )
                        lines = [f"{i+1}. {p}: {v} pts" for i, (p, v) in enumerate(ranked)]
                        tg_send_message("📊 All 6 games done! Leaderboard updated:\n" + "\n".join(lines))
                    except Exception:
                        tg_send_message("📊 All games finished — season points and stats updated automatically.")

            save_notify_state(state)
        except Exception:
            pass
        time.sleep(cfg.get("poll_seconds", 30))

def start_notifier_once():
    global _notifier_started
    if _notifier_started: return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        t = threading.Thread(target=notifier_loop, daemon=True)
        t.start()
        _notifier_started = True

start_notifier_once()
if __name__ == "__main__":
    # When running directly, enable debug mode for easier development.
    # Listen on port 8194 instead of the previous default of 8000/8094.
    # The port can be overridden by setting the PORT environment variable.
    port = int(os.environ.get("PORT", 8194))
    app.run(host="0.0.0.0", port=port, debug=True)

@app.route("/notify")
def notify_page():
    return render_template("notify.html", app_version=APP_VERSION)

@app.route("/update_telegram", methods=["POST"])
def update_telegram():
    data = request.get_json(silent=True) or {}
    # Accept both "token" and "telegram_bot_token" keys for backwards compatibility
    token = (data.get("token") or data.get("telegram_bot_token") or "").strip()
    chat_id = (data.get("chat_id") or data.get("telegram_chat_id") or "").strip()
    if not token or not chat_id:
        return jsonify({"success": False, "message": "Missing token or chat ID."}), 400
    try:
        # Load existing settings to preserve other keys
        settings = load_settings()
        settings["telegram_enabled"] = True
        settings["telegram_bot_token"] = token
        settings["telegram_chat_id"] = chat_id
        # Ensure poll_seconds has a sensible default
        if not settings.get("poll_seconds"):
            settings["poll_seconds"] = DEFAULT_TELEGRAM.get("poll_seconds", 30)
        save_settings(settings)
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error saving settings: {ex}"}), 500
    return jsonify({"success": True, "message": "Telegram settings saved successfully."})


@app.route("/update_wa", methods=["POST"])
def update_wa():
    """Enable or disable WhatsApp notifications."""
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("wa_enabled", False))
    s = load_settings()
    s["wa_enabled"] = enabled
    save_settings(s)
    return jsonify({"success": True, "wa_enabled": enabled})

@app.route("/wa_status")
def wa_status():
    """Return current WhatsApp bridge status and enabled setting."""
    s = load_settings()
    bridge_ok = False
    try:
        r = requests.get("http://172.17.0.1:8097/status", timeout=3)
        bridge_ok = r.ok and r.json().get("connected", False)
    except Exception:
        pass
    return jsonify({
        "wa_enabled": s.get("wa_enabled", False),
        "bridge_connected": bridge_ok,
        "group_jid": os.environ.get("WA_GROUP_JID", "(not set)"),
    })

@app.route("/test_telegram", methods=["POST"])
def test_telegram():
    try:
        # Try to read runtime or saved Telegram credentials
        settings = tg_settings() if 'tg_settings' in globals() else {}
        token = (settings.get("telegram_bot_token") or settings.get("token") or "").strip()
        chat_id = (settings.get("telegram_chat_id") or settings.get("chat_id") or "").strip()
        # Fallback to saved settings if missing
        if not token or not chat_id:
            t2, c2 = _load_saved_telegram()
            token = token or t2
            chat_id = chat_id or c2
        if not token or not chat_id:
            return jsonify({"success": False, "message": "Missing token or chat_id. Save them first on the Notify page."}), 400
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "BTTS Test Notification ✅").strip()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        r = requests.post(url, json=payload, timeout=10)
        ok = False
        msg = f"HTTP {r.status_code}"
        try:
            j = r.json()
            ok = bool(j.get("ok"))
            if not ok and "description" in j:
                msg += f" — {j['description']}"
        except Exception:
            pass
        if ok:
            return jsonify({"success": True, "message": "Test message sent."})
        return jsonify({"success": False, "message": f"Failed to send. {msg}"}), 502
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error: {ex}"}), 500
        return jsonify({"success": False, "message": f"Failed to send. {msg}"}), 502
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error: {ex}"}), 500


def _load_saved_telegram():
    """Read the Telegram bot token and chat ID from the settings file.

    Returns a tuple of (token, chat_id).  This function is used as a
    fallback by endpoints such as test_telegram and telegram_status.
    It reads the consolidated settings file (SETTINGS_FILE) rather than a
    separate settings.json.  Supported keys are 'telegram_bot_token'
    and 'telegram_chat_id'.  For legacy compatibility the function
    will also return values stored under the older keys 'telegram_token'
    and 'telegram_chat_id' if present.
    """
    try:
        with open(SETTINGS_FILE, "r") as f:
            s = json.load(f)
        if not isinstance(s, dict):
            return ("", "")
        token = s.get("telegram_bot_token") or s.get("telegram_token") or ""
        chat_id = s.get("telegram_chat_id") or s.get("chat_id") or ""
        return (str(token).strip(), str(chat_id).strip())
    except Exception:
        return ("", "")


@app.route("/telegram_status", methods=["GET"])
def telegram_status():
    try:
        settings = tg_settings() if 'tg_settings' in globals() else {"token":"", "chat_id":""}
        token = (settings.get("token") or "").strip()
        chat_id = (settings.get("chat_id") or "").strip()
        t2, c2 = _load_saved_telegram()
        token_eff = token or t2
        chat_eff = chat_id or c2
        def mask(t): 
            if not t: return ""
            if len(t) <= 6: return "*"*len(t)
            return t[:6] + "..." + t[-4:]
        return jsonify({
            "env_or_runtime_token_present": bool(token),
            "env_or_runtime_chat_present": bool(chat_id),
            "saved_token_present": bool(t2),
            "saved_chat_present": bool(c2),
            "effective_token_masked": mask(token_eff),
            "effective_chat_id": chat_eff
        })
    except Exception as ex:
        return jsonify({"success": False, "message": f"Error: {ex}"}), 500
