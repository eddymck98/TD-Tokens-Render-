import os
from datetime import datetime, timezone
import random
import pandas as pd
import plotly.graph_objects as go
import resend
import requests
from streamlit_cookies_controller import CookieController
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="Touchdown Tokens",
    page_icon="🏈",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Initialize the persistent cookie controller
controller = CookieController()

# --- RESEND API & SUPABASE CONFIGURATION ---
resend.api_key = os.environ.get("RESEND_API_KEY") or st.secrets.get(
    "RESEND_API_KEY", ""
)

# --- PROFANITY & SWEAR WORD FILTER CONFIGURATION ---
PROFANITY_FILTER = [
    "damn",
    "hell",
    "crap",
    "shit",
    "fuck",
    "bitch",
    "asshole",
    "dick",
    "cunt",
    "bastard",
]


def contains_profanity(text: str) -> bool:
  if not text:
    return False
  text_lower = text.lower()
  words = text_lower.split()
  for p_word in PROFANITY_FILTER:
    if p_word in text_lower or any(p_word == w for w in words):
      return True
  return False


# --- RESEND EMAIL HELPER FUNCTION ---
def send_verification_email(to_email, verification_link):
  try:
    html_content = f"""
        <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                
                <!-- Header / Logo Area with Embedded Image -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" />
                    <h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                    <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p>
                </div>

                <!-- Body Content -->
                <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3>
                <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                    Thanks for registering an account with Touchdown Tokens. To lock in your weekly picks, compete on leaderboards, and claim your tokens, please authorise your email address below:
                </p>

                <!-- Action Button -->
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">AUTHORISE EMAIL ADDRESS</a>
                </div>

                <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">
                    If you did not request this account creation or verification, you can safely ignore and delete this email.
                </p>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">
                &copy; 2026 Touchdown Tokens. All rights reserved.
            </div>
        </div>
        """
    params = {
        "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
        "to": [to_email],
        "subject": "🏈 Authorise Your Touchdown Tokens Account",
        "html": html_content,
    }
    resend.Emails.send(params)
    return True
  except Exception as e:
    st.error(f"Failed to send verification email: {e}")
    return False


# --- SUPABASE CONFIGURATION ---
def get_supabase_client() -> Client:
  if "supabase_client" not in st.session_state:
    url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "") or st.secrets.get("SUPABASE_KEY", "")
    st.session_state.supabase_client = create_client(url, key)
  return st.session_state.supabase_client


supabase = get_supabase_client()

# --- ROBUST HANDLE QUERY & HASH PARAMS FOR PASSWORD RECOVERY ---
query_params = st.query_params

if "type" in query_params and query_params["type"] == "recovery":
  st.session_state["is_password_recovery"] = True
elif "access_token" in query_params:
  try:
    access_token = query_params["access_token"]
    refresh_token = query_params.get("refresh_token", access_token)
    supabase.auth.set_session(access_token, refresh_token)
    st.session_state["is_password_recovery"] = True
    st.query_params.clear()
  except Exception:
    pass

st.markdown(
    """
    <script>
    if (window.location.hash && window.location.hash.includes('access_token')) {
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const accessToken = hashParams.get('access_token');
        const refreshToken = hashParams.get('refresh_token') || accessToken;
        const type = hashParams.get('type');
        
        if (type === 'recovery' || accessToken) {
            const newUrl = window.location.pathname + '?access_token=' + accessToken + '&refresh_token=' + refreshToken + '&type=recovery';
            window.location.replace(newUrl);
        }
    }
    </script>
""",
    unsafe_allow_html=True,
)

# --- SECURE COOKIE-BASED AUTH PERSISTENCE ---
if "user" not in st.session_state or st.session_state.user is None:
  st.session_state.user = None
  try:
    saved_token = controller.get("td_tokens_session")
    if saved_token:
      user_response = supabase.auth.get_user(saved_token)
      if user_response and user_response.user:
        st.session_state.user = user_response.user
        try:
          supabase.auth.set_session(saved_token, saved_token)
        except Exception:
          pass

    if st.session_state.user is None:
      current_session = supabase.auth.get_session()
      if current_session and current_session.user:
        st.session_state.user = current_session.user
  except Exception:
    pass

if "form_refresh" not in st.session_state:
  st.session_state.form_refresh = 0

if "signup_success_email" not in st.session_state:
  st.session_state.signup_success_email = None


# --- CACHED HELPERS FOR ADMIN & PERFORMANCE ---
@st.cache_data(ttl=30)
def get_cached_profiles():
  res = (
      supabase.table("profiles")
      .select(
          "id, full_name, tokens, favorite_team, is_admin, avatar_emoji,"
          " avatar_border, avatar_color, selected_title, featured_badges,"
          " unlocked_badges, favorite_player, bio, default_league_view,"
          " email_notifications, high_contrast_mode, reduced_motion"
      )
      .execute()
  )
  return res.data if res.data else []


@st.cache_data(ttl=30)
def get_cached_weekly_questions(w_num):
  res = (
      supabase.table("weekly_questions")
      .select("*")
      .eq("week_number", w_num)
      .order("question_number")
      .execute()
  )
  return res.data if res.data else []


@st.cache_data(ttl=30)
def get_cached_all_weekly_questions_meta():
  res = (
      supabase.table("weekly_questions")
      .select("week_number, question_number, winning_answer")
      .neq("week_number", 999)
      .neq("week_number", 998)
      .neq("week_number", 997)
      .neq("week_number", 96)
      .execute()
  )
  return res.data if res.data else []


# --- TRUE GLOBAL TOKEN CALCULATOR ---
def get_true_global_token_balance(target_user_id):
  try:
    u_bets = (
        supabase.table("user_bets")
        .select("week_number, wager_amount, pick, weekly_questions(winning_answer)")
        .eq("user_id", target_user_id)
        .execute()
        .data
    )
    u_td = (
        supabase.table("touchdown_picks")
        .select("week_number, is_correct")
        .eq("user_id", target_user_id)
        .eq("is_correct", True)
        .execute()
        .data
    )

    td_wins_map = {td["week_number"]: 5 for td in u_td}

    curr_tokens = 10
    if u_bets or td_wins_map:
      all_weeks_involved = sorted(
          list(
              set(
                  [b["week_number"] for b in u_bets]
                  + list(td_wins_map.keys())
              )
          )
      )
      for w in all_weeks_involved:
        w_bets = [b for b in u_bets if b["week_number"] == w]
        for b in w_bets:
          w_ans = b.get("weekly_questions", {}).get("winning_answer")
          if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
              curr_tokens += b["wager_amount"]
            else:
              curr_tokens -= b["wager_amount"]
        if w in td_wins_map:
          curr_tokens += 5
    return max(0, curr_tokens)
  except Exception:
    return 10


# --- ROBUST TOKEN RECALCULATOR ---
def recalculate_all_user_balances(supabase_client):
  admin_supabase = supabase_client
  try:
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
    url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
    if service_key and url:
      admin_supabase = create_client(url, service_key)
  except Exception:
    pass

  all_users = (
      admin_supabase.table("profiles").select("id, full_name, tokens").execute().data
  )
  if not all_users:
    return

  closed_week_rows = (
      admin_supabase.table("weekly_questions")
      .select("week_number")
      .eq("question_number", 96)
      .eq("winning_answer", "CLOSED")
      .execute()
      .data
  )
  closed_weeks = [r["week_number"] for r in closed_week_rows]

  if not closed_weeks:
    return

  all_bets = admin_supabase.table("user_bets").select("*").execute().data
  all_questions = (
      admin_supabase.table("weekly_questions")
      .select("id, week_number, winning_answer")
      .execute()
      .data
  )
  all_tds = admin_supabase.table("touchdown_picks").select("*").execute().data

  q_map = {
      q["id"]: str(q.get("winning_answer", "")).strip() for q in all_questions
  }
  user_net_changes = {u["id"]: 0 for u in all_users}

  for b in all_bets:
    w_num = b.get("week_number")
    if w_num in closed_weeks:
      uid = b["user_id"]
      q_id = b.get("question_id")
      wager = int(b.get("wager_amount", 0))
      pick = str(b.get("pick", "")).strip().lower()
      w_ans = q_map.get(q_id, "").lower()

      if uid in user_net_changes and w_ans in ["yes", "no"]:
        if pick == w_ans:
          user_net_changes[uid] += wager
        else:
          user_net_changes[uid] -= wager

  for td in all_tds:
    w_num = td.get("week_number")
    if w_num in closed_weeks:
      uid = td["user_id"]
      is_c = td.get("is_correct")
      if uid in user_net_changes and str(is_c).lower() == "true":
        user_net_changes[uid] += 5

  for uid, net_change in user_net_changes.items():
    final_balance = max(0, 10 + net_change)
    admin_supabase.table("profiles").update({"tokens": final_balance}).eq(
        "id", uid
    ).execute()


@st.cache_data
def get_static_nfl_team_data():
  return {
      "🏈 Free Agent / Neutral": {
          "logo": (
              "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true"
          ),
          "color": "#fbbf24",
          "stadium": (
              "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Arizona Cardinals": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png",
          "color": "#97233F",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Atlanta Falcons": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png",
          "color": "#A71930",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟣 Baltimore Ravens": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
          "color": "#241773",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Buffalo Bills": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
          "color": "#00338D",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 Carolina Panthers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png",
          "color": "#0085CA",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟠 Chicago Bears": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png",
          "color": "#C83803",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟠 Cincinnati Bengals": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png",
          "color": "#FB4F14",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟤 Cleveland Browns": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png",
          "color": "#FF3C00",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 Dallas Cowboys": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
          "color": "#003594",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟠 Denver Broncos": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png",
          "color": "#FB4F14",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 Detroit Lions": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png",
          "color": "#0076B6",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟢 Green Bay Packers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png",
          "color": "#203731",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Houston Texans": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png",
          "color": "#03202F",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 Indianapolis Colts": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png",
          "color": "#002C5F",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🐆 Jacksonville Jaguars": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png",
          "color": "#006778",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Kansas City Chiefs": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
          "color": "#E31837",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🪙 Las Vegas Raiders": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png",
          "color": "#A5ACAF",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "⚡ Los Angeles Chargers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png",
          "color": "#0080C6",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟡 Los Angeles Rams": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png",
          "color": "#003594",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🐬 Miami Dolphins": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
          "color": "#008E97",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟣 Minnesota Vikings": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png",
          "color": "#4F2683",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 New England Patriots": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png",
          "color": "#002244",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "⚜️ New Orleans Saints": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png",
          "color": "#D3BC8D",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 New York Giants": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png",
          "color": "#0B2265",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟢 New York Jets": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png",
          "color": "#125740",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🦅 Philadelphia Eagles": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
          "color": "#004C54",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟡 Pittsburgh Steelers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
          "color": "#FFB612",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 San Francisco 49ers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
          "color": "#AA0000",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🟢 Seattle Seahawks": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png",
          "color": "#69BE28",
          "stadium": (
              "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Tampa Bay Buccaneers": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png",
          "color": "#D50A0A",
          "stadium": (
              "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔵 Tennessee Titans": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png",
          "color": "#4B92DB",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
      "🔴 Washington Commanders": {
          "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png",
          "color": "#5A1414",
          "stadium": (
              "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"
          ),
      },
  }


NFL_TEAM_DATA = get_static_nfl_team_data()
NFL_TEAMS = list(NFL_TEAM_DATA.keys())
AVATAR_OPTIONS = [
    "🏈",
    "🐐",
    "⚡",
    "👑",
    "🎯",
    "💣",
    "💎",
    "🔥",
    "🛡️",
    "🚀",
    "🦁",
    "🐯",
    "🐻",
    "🦅",
    "🐺",
    "🦈",
    "🐉",
    "💀",
    "👽",
    "🤖",
    "⭐",
    "🏆",
    "🥇",
    "💪",
    "🎲",
    "🎩",
    "🍻",
    "🍕",
    "🍔",
    "💥",
    "🔮",
    "🃏",
    "🥷",
    "🧙‍♂️",
    "🧛‍♂️",
    "🧟‍♂️",
    "🦸‍♂️",
    "🦹‍♂️",
]

BORDER_STYLE_OPTIONS = {
    "Classic Solid": "solid",
    "Double Neon Pulse": "double",
    "Dashed Gridiron": "dashed",
    "Stealth Dotted": "dotted",
    "Championship Ridge": "ridge",
    "Groove Outlined": "inset",
}

AVAILABLE_TITLES = {
    "🏈 Gridiron Contender": {
        "badge": None,
        "req": "Default baseline title for all players.",
    },
    "👑 League Champion": {
        "badge": "🏆 League Champion",
        "req": "Be crowned the official end-of-season League Champion.",
    },
    "⭐ League Commissioner": {
        "badge": "⭐ League Commissioner",
        "req": "Create or administer a custom mini-league.",
    },
    "🔮 The Oracle": {
        "badge": "🔮 Oracle of Delphi",
        "req": "Successfully call a 5+ token wager correctly 4 weeks in a row.",
    },
    "💰 Token Tycoon": {
        "badge": "🚀 Token Tycoon",
        "req": "Reach a balance of 30+ tokens.",
    },
    "⚡ Gridiron Prophet": {
        "badge": "⚡ Gridiron Prophet",
        "req": "Correctly predict 5+ Touchdown Scorers across the season.",
    },
    "🎯 Sharp Shooter": {
        "badge": "🎯 Sniper",
        "req": "Correctly predict 3+ Touchdown Scorers across the season.",
    },
    "🏈 TD Specialist": {
        "badge": "🏈 TD Guru",
        "req": "Correctly predict 2+ Touchdown Scorers.",
    },
    "📉 Bankrupt Gambler": {
        "badge": "📉 Down Bad",
        "req": "Reach a token balance of 0 tokens.",
    },
}

MASTER_BADGES = {
    "🚀 Token Tycoon": "Reach a balance of 30+ tokens",
    "🎯 High Roller": "Wager 10+ tokens on a single question",
    "⚡ Double Down Legend": "Wager 15+ total tokens in a single week",
    "💣 All-In Maverick": "Wager 100% of your remaining token balance on a slate",
    "🏈 TD Guru": "Correctly predict 2+ Touchdown Scorers",
    "🎯 Sniper": "Correctly predict 3+ Touchdown Scorers across the season",
    "👑 Weekly High Scorer": "Win the most net tokens in a single week",
    "🎯 Perfect 10/10": "Correctly answer all 10 scenarios in a single week",
    "🧊 Clutch Gene": (
        "Win a scenario where 75%+ of the league picked the wrong side"
    ),
    "🛡️ Iron Defender": "Submit bets for 5 or more weeks without missing",
    "💰 Century Club": "Accumulate 100+ total cumulative tokens won across history",
    "📉 Wall Street Bets": "Take the largest token loss in a single week",
    "📉 Down Bad": "Reach a token balance of 0 tokens",
    "🏆 League Champion": "Be crowned the official end-of-season League Champion",
    "⭐ League Commissioner": "Create or administer a custom mini-league",
    "🔮 Oracle of Delphi": (
        "Successfully call a 5+ token wager correctly 4 weeks in a row"
    ),
    "🔥 Untouchable Run": "Gain 20+ net tokens in a single weekly slate",
    "⚡ Gridiron Prophet": (
        "Correctly predict 5+ Touchdown Scorers across the season"
    ),
    "💎 Diamond Hands": (
        "Survive with fewer than 3 tokens remaining and bounce back to 30+"
    ),
}

DEFAULT_QUESTION_TEMPLATES = [
    "Will QB 1 throw for over 250+ passing yards?",
    "Will RB 1 rush for 75+ rushing yards?",
    "Will WR 1 catch 6 or more receptions?",
    "Will Away Team score a touchdown in the 1st quarter?",
    "Will there be a successful 50+ yard Field Goal kicked?",
    "Will this game have over 45.5 combined points scored?",
    "Will any Defense record a pick-six or fumble recovery touchdown?",
    "Will TE 1 score a rushing or receiving touchdown?",
    "Will this game go into Overtime?",
    "Will Home Team record 3 or more sacks?",
]

user_team_color = "#fbbf24"
user_team_logo = (
    "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true"
)
user_stadium_bg = (
    "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"
)

if st.session_state.user:
  try:
    res = (
        supabase.table("profiles")
        .select("favorite_team")
        .eq("id", st.session_state.user.id)
        .single()
        .execute()
    )
    if res.data:
      t_name = res.data.get("favorite_team", "🏈 Free Agent / Neutral")
      t_info = NFL_TEAM_DATA.get(
          t_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
      )
      user_team_color = t_info["color"]
      user_team_logo = t_info["logo"]
      user_stadium_bg = t_info["stadium"]
  except Exception:
    pass

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=Teko:wght@500;700&display=swap');

    .stMainBlockContainer, div[data-testid="stMainBlockContainer"] {{
        padding-top: 1rem !important;
    }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    .stApp, div[data-testid="stAppViewContainer"] {{
        background: 
            radial-gradient(circle at 50% 20%, rgba(15, 23, 42, 0.90), rgba(7, 13, 25, 0.99)),
            url('{user_team_logo}') center center / 28% no-repeat fixed,
            url('{user_stadium_bg}') center center / cover no-repeat fixed !important;
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif !important;
    }}
    
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #030712 0%, #0b0f19 100%) !important;
        border-right: 3px solid {user_team_color} !important;
        font-family: 'Inter', sans-serif !important;
        box-shadow: 6px 0 30px rgba(0,0,0,0.7);
    }}
    
    a, a:visited, a:hover, a:active {{
        color: #38bdf8 !important;
        text-decoration: underline !important;
    }}
    
    p, span, label, div[data-testid="stMarkdownContainer"] {{
        color: #f8fafc !important;
    }}

    .nfl-header {{ text-align: center; padding: 0px 0 4px 0; margin-top: -25px; }}
    .nfl-subtitle {{
        font-family: 'Teko', sans-serif;
        font-size: 24px;
        letter-spacing: 5px;
        color: #93c5fd;
        text-transform: uppercase;
        margin-top: -4px;
        text-shadow: 0 2px 10px rgba(0,0,0,0.8);
    }}
    .header-logo {{
        width: 240px;
        filter: drop-shadow(0px 10px 22px {user_team_color}cc);
        border-radius: 12px;
    }}
    
    @keyframes teamPulse {{
        0% {{ box-shadow: 0 0 12px {user_team_color}33; }}
        50% {{ box-shadow: 0 0 32px {user_team_color}bb; }}
        100% {{ box-shadow: 0 0 12px {user_team_color}33; }}
    }}

    .sticky-balance-bar {{
        position: sticky;
        top: 0;
        z-index: 999;
        background: rgba(15, 23, 42, 0.94);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-bottom: 3px solid {user_team_color};
        padding: 10px 22px;
        margin-top: 4px;
        margin-bottom: 20px;
        border-radius: 0 0 16px 16px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.7);
    }}

    .big-token-card {{
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.88) 0%, rgba(6, 10, 18, 0.94) 100%);
        padding: 32px;
        border-radius: 20px;
        color: #ffffff !important;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-top: 3px solid {user_team_color};
        margin-bottom: 25px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 10px 35px rgba(0,0,0,0.5);
        animation: teamPulse 3.5s infinite ease-in-out;
    }}
    .big-token-number {{
        font-family: 'Bebas Neue', sans-serif;
        font-size: 78px;
        letter-spacing: 3px;
        margin: 0;
        color: {user_team_color} !important;
        text-shadow: 0px 6px 20px {user_team_color}99;
    }}

    .champion-card {{
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.92) 0%, rgba(180, 83, 9, 0.92) 50%, rgba(245, 158, 11, 0.92) 100%);
        padding: 32px;
        border-radius: 18px;
        color: #ffffff !important;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-top: 4px solid #fbbf24;
        margin-bottom: 30px;
        backdrop-filter: blur(14px);
        box-shadow: 0 10px 35px rgba(0,0,0,0.6);
        animation: teamPulse 2s infinite ease-in-out;
    }}

    .mvp-banner {{
        background: linear-gradient(135deg, rgba(147, 51, 234, 0.90) 0%, rgba(30, 58, 138, 0.94) 100%);
        border: 1px solid rgba(192, 132, 252, 0.4);
        border-top: 3px solid #c084fc;
        padding: 22px;
        border-radius: 16px;
        margin-bottom: 22px;
        text-align: center;
        backdrop-filter: blur(14px);
        box-shadow: 0 10px 30px rgba(192, 132, 252, 0.35);
    }}

    .trophy-card-unlocked {{
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.90) 0%, rgba(15, 23, 42, 0.94) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-left: 4px solid {user_team_color};
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 14px;
        backdrop-filter: blur(12px);
        box-shadow: 0 6px 18px rgba(0,0,0,0.4);
    }}

    .trophy-card-locked {{
        background: rgba(15, 23, 42, 0.55);
        border: 1px dashed rgba(255, 255, 255, 0.18);
        padding: 16px;
        border-radius: 14px;
        margin-bottom: 14px;
        opacity: 0.55;
    }}

    .leaderboard-row {{
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 6px 12px;
        margin-bottom: 6px;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .leaderboard-row:hover {{
        transform: translateY(-1px);
        border-color: rgba(255, 255, 255, 0.25);
        box-shadow: 0 4px 15px {user_team_color}33;
    }}

    .podium-rank-1 {{
        border: 1px solid rgba(251, 191, 36, 0.5) !important;
        border-left: 4px solid #fbbf24 !important;
        background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important;
    }}
    .podium-rank-2 {{
        border: 1px solid rgba(148, 163, 184, 0.5) !important;
        border-left: 4px solid #94a3b8 !important;
        background: linear-gradient(135deg, rgba(148, 163, 184, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important;
    }}
    .podium-rank-3 {{
        border: 1px solid rgba(180, 83, 9, 0.5) !important;
        border-left: 4px solid #b45309 !important;
        background: linear-gradient(135deg, rgba(180, 83, 9, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important;
    }}

    .stat-pill-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 2px;
    }}
    .stat-pill {{
        background: rgba(30, 41, 59, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 0px 6px;
        font-size: 9px;
        font-weight: 600;
        color: #cbd5e1;
        display: inline-flex;
        align-items: center;
        gap: 3px;
    }}

    .vs-card {{
        background: rgba(15, 23, 42, 0.90);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-top: 3px solid {user_team_color};
        padding: 22px;
        border-radius: 16px;
        text-align: center;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 35px rgba(0,0,0,0.5);
    }}

    .matchup-team-title {{
        font-family: 'Teko', sans-serif;
        font-size: 24px;
        letter-spacing: 1.5px;
        color: #fbbf24;
        text-transform: uppercase;
    }}

    .timer-card {{
        background: rgba(15, 23, 42, 0.90);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-top: 3px solid {user_team_color};
        padding: 18px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 22px;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 35px rgba(0,0,0,0.5);
    }}

    .chat-bubble {{
        background-color: rgba(15, 23, 42, 0.88);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        padding: 14px 18px;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }}

    .summary-box {{
        background-color: rgba(15, 23, 42, 0.88) !important;
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left: 4px solid {user_team_color} !important;
        padding: 20px;
        border-radius: 14px;
        color: #f8fafc !important;
        margin-top: 16px;
        box-shadow: 0 8px 28px rgba(0,0,0,0.35);
    }}

    .rule-card {{
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.82) 0%, rgba(15, 23, 42, 0.92) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-top: 3px solid {user_team_color};
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }}
    .rule-step-num {{
        font-family: 'Bebas Neue', sans-serif;
        font-size: 28px;
        color: {user_team_color};
        letter-spacing: 2px;
        margin-bottom: 4px;
    }}

    div[data-testid="stHorizontalBlock"] div[data-baseweb="tab-list"],
    div[data-baseweb="tab-list"] {{
        gap: 6px;
        background-color: rgba(11, 15, 25, 0.6);
        padding: 6px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        margin-bottom: 20px;
        overflow-x: auto;
    }}

    button[data-baseweb="tab"] {{
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        padding: 8px 14px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    
    button[data-baseweb="tab"]:hover {{
        background: rgba(30, 41, 59, 0.9) !important;
        border-color: rgba(255, 255, 255, 0.2) !important;
        transform: translateY(-1px);
    }}

    button[data-baseweb="tab"] * {{
        font-family: 'Teko', sans-serif !important;
        font-size: 19px !important;
        letter-spacing: 1.2px !important;
        color: #94a3b8 !important;
    }}

    button[aria-selected="true"] {{
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        border-top: 3px solid {user_team_color} !important;
        box-shadow: 0 6px 20px {user_team_color}44 !important;
    }}

    button[aria-selected="true"] * {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}

    .stSelectbox div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"],
    [data-baseweb="input"],
    [data-baseweb="tag"] {{
        background-color: rgba(15, 23, 42, 0.90) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }}
    div[data-baseweb="select"] span, 
    div[data-baseweb="select"] div,
    ul[data-baseweb="menu"],
    li[data-baseweb="option"],
    div[role="listbox"],
    div[role="dialog"] {{
        background-color: #0f172a !important;
        color: #ffffff !important;
    }}
    div[role="option"]:hover {{
        background-color: #1e3a8a !important;
        color: #38bdf8 !important;
    }}

    div.stButton > button,
    div.stButton > button:active,
    div.stButton > button:focus,
    button[kind="secondary"],
    button[kind="secondary"]:active,
    button[kind="secondary"]:focus {{
        background-color: rgba(30, 41, 59, 0.9) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        font-family: 'Teko', sans-serif !important;
        font-size: 22px !important;
    }}
    div.stButton > button:hover {{
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
    }}

    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {{
        background: linear-gradient(135deg, {user_team_color} 0%, #d97706 100%) !important;
        color: #000000 !important;
        font-family: 'Teko', sans-serif !important;
        font-size: 25px !important;
        letter-spacing: 2px !important;
        text-transform: uppercase !important;
        border-radius: 12px !important;
        border: none !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.5);
    }}
    div.stButton > button[kind="primary"]:hover, div.stFormSubmitButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 30px {user_team_color}99 !important;
    }}

    details[data-testid="stExpander"] {{
        background-color: rgba(15, 23, 42, 0.85) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 12px !important;
    }}
    details[data-testid="stExpander"] summary {{
        color: #f8fafc !important;
    }}
    details[data-testid="stExpander"] summary:hover {{
        color: #38bdf8 !important;
    }}

    .stTextInput > label, .stNumberInput > label, .stRadio > label, .stSelectbox > label {{
        color: #f8fafc !important;
        font-weight: 600 !important;
        font-size: 16px !important;
        letter-spacing: 0.5px;
    }}
    .stTextInput input, .stNumberInput input {{
        background-color: rgba(15, 23, 42, 0.92) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 12px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="nfl-header">
        <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" class="header-logo" alt="Touchdown Tokens Logo" />
        <div class="nfl-subtitle">Weekly NFL Predictions & Wagers</div>
    </div>
""",
    unsafe_allow_html=True,
)


def sync_and_get_user_badges(target_user_id, check_celebration=False):
  try:
    p_res = (
        supabase.table("profiles")
        .select("tokens, unlocked_badges")
        .eq("id", target_user_id)
        .single()
        .execute()
    )
    p_data = p_res.data
    if not p_data:
      return []
  except Exception:
    return []

  toks = get_true_global_token_balance(target_user_id)
  existing_unlocked = p_data.get("unlocked_badges")
  if not isinstance(existing_unlocked, list):
    existing_unlocked = []

  u_bets = (
      supabase.table("user_bets")
      .select("*, weekly_questions(winning_answer)")
      .eq("user_id", target_user_id)
      .execute()
      .data
  )
  u_td = (
      supabase.table("touchdown_picks")
      .select("*")
      .eq("user_id", target_user_id)
      .eq("is_correct", True)
      .execute()
      .data
  )

  newly_earned = set(existing_unlocked)

  my_administered = (
      supabase.table("leagues")
      .select("id")
      .eq("created_by", target_user_id)
      .execute()
      .data
  )
  if my_administered or p_data.get("is_admin"):
    newly_earned.add("⭐ League Commissioner")

  if toks >= 30:
    newly_earned.add("🚀 Token Tycoon")
  if any(b["wager_amount"] >= 10 for b in u_bets):
    newly_earned.add("🎯 High Roller")
  if len(u_td) >= 2:
    newly_earned.add("🏈 TD Guru")
  if len(u_td) >= 3:
    newly_earned.add("🎯 Sniper")
  if len(u_td) >= 5:
    newly_earned.add("⚡ Gridiron Prophet")
  if toks == 0:
    newly_earned.add("📉 Down Bad")

  weeks_played = set()
  total_lifetime_won = 0
  weekly_nets = {}

  for b in u_bets:
    w_num = b["week_number"]
    weeks_played.add(w_num)
    w_ans = b.get("weekly_questions", {}).get("winning_answer")

    if w_num not in weekly_nets:
      weekly_nets[w_num] = {"gains": 0, "losses": 0, "large_wager_hits": 0}

    if w_ans in ["Yes", "No"]:
      if b["pick"] == w_ans:
        total_lifetime_won += b["wager_amount"]
        weekly_nets[w_num]["gains"] += b["wager_amount"]
        if b["wager_amount"] >= 5:
          weekly_nets[w_num]["large_wager_hits"] += 1
      else:
        weekly_nets[w_num]["losses"] += b["wager_amount"]

  for td in u_td:
    w_num = td["week_number"]
    if w_num in weekly_nets:
      weekly_nets[w_num]["gains"] += 5

  sorted_weeks = sorted(list(weekly_nets.keys()))
  consecutive_oracle_weeks = 0
  for w in sorted_weeks:
    w_slate_bets = [b for b in u_bets if b["week_number"] == w]
    has_large_win = any(
        b["wager_amount"] >= 5
        and b["pick"] == b.get("weekly_questions", {}).get("winning_answer")
        for b in w_slate_bets
    )
    if has_large_win:
      consecutive_oracle_weeks += 1
      if consecutive_oracle_weeks >= 4:
        newly_earned.add("🔮 Oracle of Delphi")
    else:
      consecutive_oracle_weeks = 0

  for w, w_data in weekly_nets.items():
    net_w_tokens = w_data["gains"] - w_data["losses"]
    if net_w_tokens >= 20:
      newly_earned.add("🔥 Untouchable Run")

  if toks >= 30:
    sim_tokens = 10
    ever_low = False
    for w in sorted_weeks:
      if sim_tokens < 3:
        ever_low = True
      w_data = weekly_nets[w]
      sim_tokens += w_data["gains"] - w_data["losses"]
    if ever_low:
      newly_earned.add("💎 Diamond Hands")

  if len(weeks_played) >= 5:
    newly_earned.add("🛡️ Iron Defender")
  if total_lifetime_won >= 100:
    newly_earned.add("💰 Century Club")

  graded_q = (
      supabase.table("weekly_questions")
      .select("week_number")
      .neq("week_number", 999)
      .neq("week_number", 998)
      .neq("week_number", 997)
      .neq("week_number", 96)
      .neq("winning_answer", "Pending")
      .neq("winning_answer", "LOCKED")
      .order("week_number", desc=True)
      .execute()
      .data
  )
  if graded_q:
    latest_w = graded_q[0]["week_number"]
    all_latest_bets = (
        supabase.table("user_bets")
        .select("*, weekly_questions(winning_answer)")
        .eq("week_number", latest_w)
        .execute()
        .data
    )

    user_gains = {}
    user_loss = {}
    user_correct = {}

    for b in all_latest_bets:
      u = b["user_id"]
      w_ans = b.get("weekly_questions", {}).get("winning_answer")
      if u not in user_gains:
        user_gains[u] = 0
        user_loss[u] = 0
        user_correct[u] = 0

      if w_ans in ["Yes", "No"]:
        if b["pick"] == w_ans:
          user_gains[u] += b["wager_amount"]
          user_correct[u] += 1
        else:
          user_loss[u] += b["wager_amount"]

    if user_gains and max(user_gains.values(), default=-1) > 0:
      if max(user_gains, key=user_gains.get) == target_user_id:
        newly_earned.add("👑 Weekly High Scorer")

    if user_loss and max(user_loss.values(), default=-1) > 0:
      if max(user_loss, key=user_loss.get) == target_user_id:
        newly_earned.add("📉 Wall Street Bets")

    if user_correct.get(target_user_id, 0) == 10:
      newly_earned.add("🎯 Perfect 10/10")

  final_badges_list = list(newly_earned)

  if set(final_badges_list) != set(existing_unlocked):
    try:
      supabase.table("profiles").update(
          {"unlocked_badges": final_badges_list}
      ).eq("id", target_user_id).execute()
    except Exception:
      pass

  if check_celebration and target_user_id == st.session_state.user.id:
    cache_key = f"seen_badges_{target_user_id}"
    if cache_key not in st.session_state:
      st.session_state[cache_key] = final_badges_list
    else:
      newly_detected = [
          b for b in final_badges_list if b not in st.session_state[cache_key]
      ]
      if newly_detected:
        st.balloons()
        for nb in newly_detected:
          st.toast(f"🏆 NEW TROPHY UNLOCKED: {nb}!", icon="🎉")
        st.session_state[cache_key] = final_badges_list

  return final_badges_list


@st.cache_data(ttl=60)
def get_earned_title(target_user_id):
  try:
    prof_res = (
        supabase.table("profiles")
        .select("selected_title")
        .eq("id", target_user_id)
        .single()
        .execute()
        .data
    )
    if prof_res and prof_res.get("selected_title"):
      saved_title = prof_res.get("selected_title")
      if saved_title in AVAILABLE_TITLES:
        return saved_title
  except Exception:
    pass

  user_badges = sync_and_get_user_badges(target_user_id)
  for title, info in AVAILABLE_TITLES.items():
    if info["badge"] and info["badge"] in user_badges:
      return title
  return "🏈 Gridiron Contender"


@st.cache_data(ttl=60)
def calculate_nemesis(target_user_id, allowed_peer_ids=None):
  try:
    user_bets = (
        supabase.table("user_bets")
        .select("week_number, question_id, pick")
        .eq("user_id", target_user_id)
        .execute()
        .data
    )
    if not user_bets:
      return "None Yet", 0

    user_picks_map = {
        (b["week_number"], b["question_id"]): b["pick"] for b in user_bets
    }
    rival_disagreements = {}

    for (w_num, q_id), u_pick in user_picks_map.items():
      other_bets_query = (
          supabase.table("user_bets")
          .select("user_id, pick, weekly_questions(winning_answer)")
          .eq("week_number", w_num)
          .eq("question_id", q_id)
          .neq("user_id", target_user_id)
      )
      if allowed_peer_ids is not None:
        if not allowed_peer_ids:
          continue
        other_bets_query = other_bets_query.in_("user_id", list(allowed_peer_ids))

      other_bets = other_bets_query.execute().data
      if other_bets:
        for ob in other_bets:
          rival_id = ob["user_id"]
          rival_pick = ob["pick"]
          winning_ans = ob.get("weekly_questions", {}).get("winning_answer")

          if rival_pick != u_pick and winning_ans in ["Yes", "No"]:
            if rival_pick == winning_ans:
              rival_disagreements[rival_id] = (
                  rival_disagreements.get(rival_id, 0) + 1
              )

    if not rival_disagreements:
      return "None Yet", 0

    nemesis_id = max(rival_disagreements, key=rival_disagreements.get)
    nemesis_score = rival_disagreements[nemesis_id]

    nemesis_prof = (
        supabase.table("profiles")
        .select("full_name")
        .eq("id", nemesis_id)
        .single()
        .execute()
        .data
    )
    nemesis_name = (
        nemesis_prof.get("full_name", "Unknown Rival")
        if nemesis_prof
        else "Unknown Rival"
    )

    return nemesis_name, nemesis_score
  except Exception:
    return "None Yet", 0


@st.cache_data(ttl=60)
def calculate_streak(target_user_id):
  try:
    u_bets = (
        supabase.table("user_bets")
        .select("week_number, pick, weekly_questions(winning_answer)")
        .eq("user_id", target_user_id)
        .order("week_number", desc=True)
        .execute()
        .data
    )
    if not u_bets:
      return "0W"

    streak = 0
    for b in u_bets:
      w_ans = b.get("weekly_questions", {}).get("winning_answer")
      if w_ans in ["Yes", "No"]:
        if b["pick"] == w_ans:
          streak += 1
        else:
          break
    return f"{streak}W" if streak > 0 else "0W"
  except Exception:
    return "0W"


@st.cache_data(ttl=60)
def get_cached_leaderboard_stats(allowed_peer_ids=None):
  leader_res = get_cached_profiles()
  stats = []
  if not leader_res:
    return stats

  for p in leader_res:
    if allowed_peer_ids is not None and p["id"] not in allowed_peer_ids:
      continue

    true_global_tokens = get_true_global_token_balance(p["id"])

    correct_tds = (
        supabase.table("touchdown_picks")
        .select("*")
        .eq("user_id", p["id"])
        .eq("is_correct", True)
        .execute()
        .data
    )
    td_count = len(correct_tds) if correct_tds else 0

    u_bets = (
        supabase.table("user_bets")
        .select("*, weekly_questions(winning_answer)")
        .eq("user_id", p["id"])
        .execute()
        .data
    )
    wins, total_graded = 0, 0
    for b in u_bets:
      w_ans = b.get("weekly_questions", {}).get("winning_answer")
      if w_ans in ["Yes", "No"]:
        total_graded += 1
        if b["pick"] == w_ans:
          wins += 1
    win_rate = int((wins / total_graded) * 100) if total_graded > 0 else 0

    nem_name, nem_score = calculate_nemesis(
        p["id"], allowed_peer_ids=allowed_peer_ids
    )
    player_streak = calculate_streak(p["id"])

    stats.append({
        **p,
        "tokens": true_global_tokens,
        "correct_tds": td_count,
        "win_rate": win_rate,
        "total_bets": total_graded,
        "nemesis_name": nem_name,
        "nemesis_score": nem_score,
        "streak": player_streak,
    })

  return sorted(stats, key=lambda x: (-x["tokens"], -x["correct_tds"], x["full_name"]))


is_signin_locked = False
is_signup_locked = False
try:
  signin_lock_setting = (
      supabase.table("weekly_questions")
      .select("winning_answer")
      .eq("week_number", 998)
      .execute()
      .data
  )
  is_signin_locked = (
      signin_lock_setting and signin_lock_setting[0]["winning_answer"] == "LOCKED"
  )
except Exception:
  pass

try:
  signup_lock_setting = (
      supabase.table("weekly_questions")
      .select("winning_answer")
      .eq("week_number", 997)
      .execute()
      .data
  )
  is_signup_locked = (
      signup_lock_setting and signup_lock_setting[0]["winning_answer"] == "LOCKED"
  )
except Exception:
  pass

# ==========================================
# 0. PASSWORD RECOVERY / RESET SCREEN INTERCEPT
# ==========================================
if st.session_state.get("is_password_recovery", False):
  st.title("Touchdown Tokens")
  st.subheader("🔑 Set a New Password")
  st.caption("Please choose a secure new password for your account.")

  with st.form("password_recovery_screen_form"):
    new_p1 = st.text_input("New Password (min 6 chars)", type="password")
    new_p2 = st.text_input("Confirm New Password", type="password")
    submit_new_pass = st.form_submit_button("Update Password & Log In 🚀", type="primary")

    if submit_new_pass:
      if len(new_p1) < 6:
        st.warning("Password must be at least 6 characters long.")
      elif new_p1 != new_p2:
        st.error("Passwords do not match.")
      else:
        try:
          supabase.auth.update_user({"password": new_p1})
          st.session_state["is_password_recovery"] = False
          st.success("Password updated successfully! You can now log in.")
          st.rerun()
        except Exception as e:
          st.error(f"Failed to update password: {e}")

  if st.button("Cancel & Return to Login"):
    st.session_state["is_password_recovery"] = False
    st.rerun()

# ==========================================
# 1. LOGIN & SIGNUP SCREEN WITH RESEND EMAIL
# ==========================================
elif st.session_state.user is None:
  st.title("Touchdown Tokens")

  if st.session_state.get("signup_success_email"):
    success_email_val = st.session_state["signup_success_email"]
    st.markdown(
        f"""
        <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 35px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 20px;">
            <h2 style="color: #fbbf24; font-family: 'Bebas Neue', Arial, sans-serif; font-size: 36px; letter-spacing: 2px; margin-bottom: 10px;">WELCOME TO THE LEAGUE! 🏈</h2>
            <p style="color: #cbd5e1; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                We have successfully created your account and sent a verification email to <b style="color: #38bdf8;">{success_email_val}</b>.
            </p>
            <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); padding: 18px; border-radius: 12px; margin-bottom: 25px; text-align: left;">
                <b style="color: #ffffff; font-size: 15px;">Next Steps & Useful Links:</b>
                <ul style="color: #cbd5e1; font-size: 14px; margin-top: 8px; margin-bottom: 0; padding-left: 20px; line-height: 1.6;">
                    <li>Check your email inbox (and spam folder) for the verification message.</li>
                    <li>Click the <b>Authorise Email Address</b> verification button inside the email.</li>
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    col_btn_back1, col_btn_back2 = st.columns(2)
    with col_btn_back1:
      if st.button("Proceed to Log In 🔒", type="primary"):
        st.session_state.signup_success_email = None
        st.rerun()
    with col_btn_back2:
      if st.button("Sign Up Another Account 📝"):
        st.session_state.signup_success_email = None
        st.rerun()

  else:
    tab_login, tab_signup = st.tabs(["🔒 Log In", "📝 Sign Up"])

    with tab_login:
      st.subheader("Login to Your Account")
      if is_signin_locked:
        st.error(
            "🔒 **SIGN-IN LOCKED:** The Admin has temporarily disabled log-ins."
            " Please check back soon!"
        )
      else:
        login_email = st.text_input("Email", key="login_email")
        login_password = st.text_input(
            "Password", type="password", key="login_password"
        )

        if st.button("Login"):
          if login_email and login_password:
            try:
              auth_response = supabase.auth.sign_in_with_password({
                  "email": login_email,
                  "password": login_password,
              })
              user = auth_response.user

              if user and user.email_confirmed_at:
                st.session_state["user"] = user
                if auth_response.session and auth_response.session.access_token:
                  controller.set(
                      "td_tokens_session",
                      auth_response.session.access_token,
                      max_age=2592000,
                  )
                st.success("Successfully logged in!")
                st.rerun()
              else:
                supabase.auth.sign_out()
                st.error(
                    "Please authorise your email first before logging in. Check"
                    " your inbox for the verification link."
                )
            except Exception:
              st.error(
                  "Invalid login credentials or unverified account. Please"
                  " authorise first."
              )
          else:
            st.warning("Please enter both email and password.")

        st.write("")
        with st.expander("🔑 Forgot Password?"):
          st.caption("Enter your email address to receive a password reset link.")
          reset_email = st.text_input(
              "Your Account Email", key="reset_email_input"
          )
          if st.button("Send Reset Link"):
            if reset_email:
              try:
                admin_supabase = supabase
                service_key = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
                url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
                
                if service_key and url:
                  admin_supabase = create_client(url, service_key)

                response = admin_supabase.auth.admin.generate_link(
                    {"type": "recovery", "email": reset_email.strip()}
                )

                if response and hasattr(response, "properties") and response.properties:
                  recovery_link = getattr(response.properties, "action_link", None)
                  
                  if not recovery_link and isinstance(response.properties, dict):
                    recovery_link = response.properties.get("action_link")

                  if recovery_link:
                    html_content = f"""
                            <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
                                <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                                    
                                    <div style="text-align: center; margin-bottom: 30px;">
                                        <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" />
                                        <h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                                        <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Password Reset Request</p>
                                    </div>

                                    <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Reset Your Password 🔑</h3>
                                    <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                                        We received a request to reset your Touchdown Tokens password. Click the secure button below to choose a brand new password for your account:
                                    </p>

                                    <div style="text-align: center; margin: 35px 0;">
                                        <a href="{recovery_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">RESET PASSWORD</a>
                                    </div>

                                    <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">
                                        If you did not request a password reset, you can safely ignore and delete this email. Your account remains completely secure.
                                    </p>
                                </div>
                                <div style="text-align: center; margin-top: 20px; color: #64748b; font-size: 12px;">
                                    &copy; 2026 Touchdown Tokens. All rights reserved.
                                </div>
                            </div>
                            """

                    params = {
                        "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                        "to": [reset_email.strip()],
                        "subject": "🔑 Reset Your Touchdown Tokens Password",
                        "html": html_content,
                    }
                    resend.Emails.send(params)
                    st.success("Password reset email sent via Resend! Check your inbox.")
                  else:
                    st.error("Could not retrieve recovery link properties from the response.")
                else:
                  st.error("Could not generate recovery link for this email.")
              except Exception as e:
                st.error(f"Error sending password reset email: {e}")
            else:
              st.warning("Please enter your email address.")

    with tab_signup:
      st.subheader("Create an Account")
      if is_signup_locked:
        st.error(
            "🔒 **SIGN-UP LOCKED:** The Admin has temporarily disabled new account"
            " registrations. Please check back soon!"
        )
      else:
        st.caption("New players start with 10 free tokens!")

        col_fn, col_sn = st.columns(2)
        with col_fn:
          reg_first_name = st.text_input("First Name", key="reg_first_name")
        with col_sn:
          reg_surname = st.text_input("Surname", key="reg_surname")

        signup_email = st.text_input("Email Address", key="signup_email")
        signup_password = st.text_input(
            "Password (min 6 chars)", type="password", key="signup_password"
        )

        st.write("")
        with st.expander(
            "📖 View Touchdown Tokens Terms of Service & User Agreement"
        ):
          st.markdown("""
                      **TOUCHDOWN TOKENS — TERMS OF SERVICE & USER AGREEMENT**

                      **1. Nature of the Platform & Virtual Currency**  
                      • *Recreational & Entertainment Purpose:* Touchdown Tokens is strictly an independent, recreational, free-to-play sports prediction and entertainment platform designed solely for amusement and community engagement among sports fans.  
                      • *Zero Cash Value:* All points, scores, standings, and virtual tokens ("Tokens") maintain zero real-world cash or monetary value and cannot be purchased, sold, bartered, or redeemed for currency, goods, or services.  
                      • *Not Gambling:* Because Tokens cannot be purchased or cashed out, the Platform does not constitute gambling, sports betting, or a lottery.

                      **2. Eligibility & Account Registration**  
                      • *Eligibility:* You represent and warrant that you are of legal age in your jurisdiction to enter into a binding contract.  
                      • *Single Account Policy:* Each user is strictly permitted to maintain one (1) active account. Multi-accounting, automated scripts, or proxy use to manipulate rankings is prohibited.  
                      • *Account Security:* You are solely responsible for maintaining the confidentiality of your credentials and all activity under your account.

                      **3. Gameplay, Submissions & Deadlines**  
                      • *Lockout Deadlines:* Weekly picks and touchdown scorer bonus selections lock strictly 15 minutes prior to the first scheduled Sunday NFL kickoff. Late submissions are not accepted.  
                      • *Final Overrides:* You may update picks freely before lockout. Your final submitted state at the moment of lockout constitutes your official, binding entry. Previous iterations are overwritten.  
                      • *Grading:* All scenario outcomes and standings are graded and finalized by the system administrator using official NFL statistics (powered by ESPN feeds). Administrative rulings are final.

                      **4. Code of Conduct & Community Standards**  
                      • *Acceptable Use:* Users must utilize the Platform in a respectful, lawful, and sportsmanlike manner.  
                      • *Prohibited Conduct:* Harassment, hate speech, threats, collusion, cheating, match-fixing, or attempting to compromise database security is strictly prohibited.  
                      • *Enforcement:* Administrators reserve the right to moderate content, deduct tokens, suspend accounts, or permanently terminate access for violations without prior notice.

                      **5. Intellectual Property Rights**  
                      • *Ownership:* All source code, design layouts, custom branding, and logos associated with Touchdown Tokens are the exclusive intellectual property of the Platform creators. Third-party team logos and sports data remain property of their respective holders.

                      **6. Disclaimers & Limitation of Liability**  
                      • *As Is Basis:* The Platform is provided on an "as is" and "as available" basis without warranties of any kind.  
                      • *Third-Party APIs:* We rely on third-party data providers (e.g., ESPN API) and assume no liability for temporary data outages, delayed stats, or initial erroneous scoring.  
                      • *Postponed/Canceled Games:* In the event an NFL game is officially postponed or canceled, connected questions are voided and token wagers are fully refunded.  
                      • *Limitation of Liability:* Administrators and hosts shall not be held liable for any direct, indirect, or consequential damages arising out of your use of the Platform.

                      **7. Modifications & Governing Law**  
                      • *Amendments:* Administrators reserve the right to modify these Terms at any time. Continued use of the Platform constitutes binding acceptance of revised terms.  
                      • *Governing Law:* These Terms are governed by and construed in accordance with the laws of the jurisdiction in which the Platform is primarily administered.
                  """)

        tc_accepted = st.checkbox(
            "I agree to the Touchdown Tokens Terms of Service & User Agreement",
            key="reg_tc_checkbox",
        )

        if st.button("Sign Up"):
          if not reg_first_name.strip():
            st.warning("Please enter your first name.")
          elif not reg_surname.strip():
            st.warning("Please enter your surname.")
          elif not signup_email.strip():
            st.warning("Please enter your email address.")
          elif not tc_accepted:
            st.warning(
                "You must accept the Terms of Service & User Agreement to create"
                " an account."
            )
          else:
            combined_full_name = (
                f"{reg_first_name.strip()} {reg_surname.strip()}"
            )
            if contains_profanity(combined_full_name):
              st.error(
                  "⚠️ Your name contains restricted language. Please choose"
                  " appropriate wording."
              )
            else:
              try:
                response = supabase.auth.sign_up({
                    "email": signup_email.strip(),
                    "password": signup_password,
                })

                if response.user:
                  new_uid = response.user.id
                  supabase.table("profiles").insert({
                      "id": new_uid,
                      "email": signup_email.strip(),
                      "full_name": combined_full_name,
                      "tokens": 10,
                      "is_admin": False,
                      "favorite_team": "🏈 Free Agent / Neutral",
                      "bio": "Ready for Kickoff!",
                      "avatar_emoji": "🏈",
                      "featured_badges": [],
                      "unlocked_badges": [],
                      "avatar_border": "solid",
                      "favorite_player": "",
                      "avatar_color": "#1e3a8a",
                      "selected_title": "🏈 Gridiron Contender",
                      "default_league_view": (
                          "00000000-0000-0000-0000-000000000001"
                      ),
                      "email_notifications": True,
                      "high_contrast_mode": False,
                      "reduced_motion": False,
                  }).execute()

                  try:
                    supabase.table("league_members").insert({
                        "league_id": "00000000-0000-0000-0000-000000000001",
                        "user_id": new_uid,
                    }).execute()
                  except Exception:
                    pass

                  verify_url = "https://tdtokens.co.uk"
                  send_verification_email(signup_email.strip(), verify_url)

                  try:
                    supabase.auth.sign_out()
                  except Exception:
                    pass

                  st.session_state.signup_success_email = signup_email.strip()
                  st.rerun()
                else:
                  st.error("Sign up failed. Please try again.")
              except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# 2. MAIN LOGGED-IN GAME PORTAL
# ==========================================
else:
  user_id = st.session_state.user.id

  try:
    profile_res = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .single()
        .execute()
    )
    profile = profile_res.data
  except Exception:
    profile = None

  if not profile:
    try:
      fallback_name = st.session_state.user.email.split("@")[0].capitalize()
      supabase.table("profiles").insert({
          "id": user_id,
          "email": st.session_state.user.email,
          "full_name": fallback_name,
          "tokens": 10,
          "is_admin": False,
          "favorite_team": "🏈 Free Agent / Neutral",
          "bio": "Ready for Kickoff!",
          "avatar_emoji": "🏈",
          "featured_badges": [],
          "unlocked_badges": [],
          "avatar_border": "solid",
          "favorite_player": "",
          "avatar_color": "#1e3a8a",
          "selected_title": "🏈 Gridiron Contender",
          "default_league_view": "00000000-0000-0000-0000-000000000001",
          "email_notifications": True,
          "high_contrast_mode": False,
          "reduced_motion": False,
      }).execute()

      try:
        supabase.table("league_members").insert({
            "league_id": "00000000-0000-0000-0000-000000000001",
            "user_id": user_id,
        }).execute()
      except Exception:
        pass

      profile_res = (
          supabase.table("profiles")
          .select("*")
          .eq("id", user_id)
          .single()
          .execute()
      )
      profile = profile_res.data
    except Exception:
      profile = {
          "id": user_id,
          "full_name": "Player",
          "tokens": 10,
          "is_admin": False,
          "favorite_team": "🏈 Free Agent / Neutral",
          "bio": "Ready for Kickoff!",
          "avatar_emoji": "🏈",
          "featured_badges": [],
          "unlocked_badges": [],
          "avatar_border": "solid",
          "favorite_player": "",
          "avatar_color": "#1e3a8a",
          "selected_title": "🏈 Gridiron Contender",
          "default_league_view": "00000000-0000-0000-0000-000000000001",
          "email_notifications": True,
          "high_contrast_mode": False,
          "reduced_motion": False,
      }

  user_avatar = profile.get("avatar_emoji", "🏈")
  user_team = profile.get("favorite_team", "🏈 Free Agent / Neutral")
  team_data = NFL_TEAM_DATA.get(
      user_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
  )
  user_border_style = profile.get("avatar_border", "solid")
  user_avatar_color = profile.get("avatar_color", "#1e3a8a")

  sync_and_get_user_badges(user_id, check_celebration=True)

  my_administered_leagues = (
      supabase.table("leagues")
      .select("id, league_name, invite_code, league_password")
      .eq("created_by", user_id)
      .execute()
      .data
  )
  is_any_league_admin = bool(my_administered_leagues) or profile.get(
      "is_admin", False
  )

  # --- SIDEBAR ---
  st.sidebar.markdown(
      f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 12px; padding: 6px 0;">
            <div style="border: 3px {user_border_style} {user_team_color}; border-radius: 12px; padding: 6px 10px; background: {user_avatar_color}; box-shadow: 0 4px 15px {user_team_color}44;">
                <span style="font-size: 34px;">{user_avatar}</span>
            </div>
            <div>
                <b style="font-size: 19px; color: #ffffff; letter-spacing: 0.3px;">{profile['full_name']}</b>
                <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">{get_earned_title(user_id)}</div>
                <div style="font-size: 12px; color: #94a3b8; font-weight: 500;">{user_team}</div>
            </div>
        </div>
    """,
      unsafe_allow_html=True,
  )
  st.sidebar.image(team_data["logo"], width=55)

  fav_player_sidebar = profile.get("favorite_player", "")
  if fav_player_sidebar:
    st.sidebar.markdown(
        f"<div style='font-size:14px; color:#38bdf8; margin-top:-4px;'>⭐ Fav"
        f" Player: <b>{fav_player_sidebar}</b></div>",
        unsafe_allow_html=True,
    )

  weeks_res = (
      supabase.table("weekly_questions")
      .select("week_number")
      .neq("week_number", 999)
      .neq("week_number", 998)
      .neq("week_number", 997)
      .neq("week_number", 96)
      .execute()
  )
  available_weeks = (
      sorted(list(set([r["week_number"] for r in weeks_res.data])))
      if weeks_res.data
      else []
  )

  true_global_tokens_sidebar = get_true_global_token_balance(user_id)
  active_tokens_display = true_global_tokens_sidebar
  if available_weeks:
    latest_w_active = available_weeks[-1]
    is_latest_graded = False
    latest_week_status = (
        supabase.table("weekly_questions")
        .select("winning_answer")
        .eq("week_number", latest_w_active)
        .eq("question_number", 96)
        .execute()
        .data
    )
    if (
        latest_week_status
        and latest_week_status[0]["winning_answer"] == "CLOSED"
    ):
      is_latest_graded = True
    else:
      w_qs_check = (
          supabase.table("weekly_questions")
          .select("winning_answer")
          .eq("week_number", latest_w_active)
          .neq("week_number", 999)
          .neq("week_number", 998)
          .neq("week_number", 997)
          .neq("week_number", 96)
          .execute()
          .data
      )
      if w_qs_check and all(
          q["winning_answer"] in ["Yes", "No"] for q in w_qs_check
      ):
        is_latest_graded = True

    if not is_latest_graded:
      user_active_bets = (
          supabase.table("user_bets")
          .select("wager_amount")
          .eq("user_id", user_id)
          .eq("week_number", latest_w_active)
          .execute()
          .data
      )
      total_wagered_active = (
          sum([b["wager_amount"] for b in user_active_bets])
          if user_active_bets
          else 0
      )
      active_tokens_display = max(
          0, true_global_tokens_sidebar - total_wagered_active
      )

  st.sidebar.metric(
      label="Available Tokens",
      value=f"{active_tokens_display} 🪙",
      help=(
          "Total True Global Tokens minus active wagers placed for the upcoming"
          " week."
      ),
  )

  if profile.get("is_admin"):
    st.sidebar.success("👑 System Admin Active")
  elif is_any_league_admin:
    st.sidebar.info("⭐ League Commissioner Active")

  st.sidebar.divider()
  if st.sidebar.button("Log Out"):
    try:
      supabase.auth.sign_out()
    except Exception:
      pass
    controller.remove("td_tokens_session")
    st.session_state.user = None
    if "supabase_client" in st.session_state:
      del st.session_state["supabase_client"]
    st.rerun()

  # --- STICKY HEADER / COMPACT BALANCE BAR ---
  st.markdown(
      f"""
        <div class="sticky-balance-bar">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="border: 3px {user_border_style} {user_team_color}; border-radius: 10px; padding: 3px 8px; background: {user_avatar_color}; box-shadow: 0 4px 12px {user_team_color}33;">
                    <span style="font-size: 26px;">{user_avatar}</span>
                </div>
                <div>
                    <b style="font-size: 16px; color: #ffffff;">{profile['full_name']}</b> <span style="font-size:11px; color:#38bdf8; margin-left:6px;">({get_earned_title(user_id)})</span>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">{user_team}</div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="text-align: right;">
                    <span style="font-family: 'Bebas Neue'; font-size: 26px; color: {user_team_color};">{active_tokens_display} 🪙</span>
                    <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Available Tokens</div>
                </div>
            </div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  if profile.get("is_admin") and is_any_league_admin:
    (
        tab_home,
        tab_profile,
        tab_rules,
        tab_bet,
        tab_history,
        tab_leagues,
        tab_league_admin,
        tab_settings,
        tab_admin,
    ) = st.tabs([
        "🏠 Home",
        "👤 Profile",
        "📖 Rules",
        "🎯 Bets",
        "📜 History",
        "🛡️ Leagues",
        "⭐ Commish",
        "⚙️ Settings",
        "🛠️ Admin",
    ])
  elif profile.get("is_admin"):
    (
        tab_home,
        tab_profile,
        tab_rules,
        tab_bet,
        tab_history,
        tab_leagues,
        tab_settings,
        tab_admin,
    ) = st.tabs([
        "🏠 Home",
        "👤 Profile",
        "📖 Rules",
        "🎯 Bets",
        "📜 History",
        "🛡️ Leagues",
        "⚙️ Settings",
        "🛠️ Admin",
    ])
  elif is_any_league_admin:
    (
        tab_home,
        tab_profile,
        tab_rules,
        tab_bet,
        tab_history,
        tab_leagues,
        tab_league_admin,
        tab_settings,
    ) = st.tabs([
        "🏠 Home",
        "👤 Profile",
        "📖 Rules",
        "🎯 Bets",
        "📜 History",
        "🛡️ Leagues",
        "⭐ Commish",
        "⚙️ Settings",
    ])
  else:
    (
        tab_home,
        tab_profile,
        tab_rules,
        tab_bet,
        tab_history,
        tab_leagues,
        tab_settings,
    ) = st.tabs([
        "🏠 Home",
        "👤 Profile",
        "📖 Rules",
        "🎯 Bets",
        "📜 History",
        "🛡️ Leagues",
        "⚙️ Settings",
    ])

  # ------------------------------------------
  # TAB 0: HOME
  # ------------------------------------------
  with tab_home:
    st.markdown(f"## Welcome back, {profile['full_name']}! 👋")

    st.markdown(
        f"""
            <div class="big-token-card">
                <div style="font-size: 18px; letter-spacing: 2px; text-transform: uppercase; color: #93c5fd;">Available Balance</div>
                <div class="big-token-number">{active_tokens_display} 🪙</div>
                <div style="font-size: 16px; color: #cbd5e1;">True Global Bank: {true_global_tokens_sidebar} 🪙 (Active Wagers Deducted)</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("👁️ Your Current Weekly Picks & Share Hub")
    st.caption(
        "Review your active entries for the upcoming week and grab a quick share"
        " text for your group chat."
    )

    if not available_weeks:
      st.info("No active weeks available.")
    else:
      view_week = st.selectbox(
          "Select Week to View",
          available_weeks,
          index=len(available_weeks) - 1,
          key="home_view_current_week_sel",
      )

      curr_user_bets = (
          supabase.table("user_bets")
          .select("*, weekly_questions(question_number, question_text)")
          .eq("user_id", user_id)
          .eq("week_number", view_week)
          .order("question_id")
          .execute()
          .data
      )
      curr_user_td = (
          supabase.table("touchdown_picks")
          .select("player_name")
          .eq("user_id", user_id)
          .eq("week_number", view_week)
          .execute()
          .data
      )

      if not curr_user_bets and not curr_user_td:
        st.warning(
            f"You haven't submitted any picks for Week {view_week} yet! Head"
            " over to the 'Place Bets' tab."
        )
      else:
        share_lines = [
            f"🏈 *{profile['full_name']} - Week {view_week} Lock-Ins* 🏈"
        ]

        for b in curr_user_bets:
          q_num = b.get("weekly_questions", {}).get("question_number", "?")
          q_txt = (
              b.get("weekly_questions", {})
              .get("question_text", "")
              .split(" | MATCHUP: ")[0]
          )
          pick_val = b["pick"]
          wager_amt = b["wager_amount"]

          st.markdown(
              f"""
                        <div class="summary-box">
                            <b>Q{q_num}: {q_txt}</b><br>
                            • Your Pick: <b style="color:{user_team_color};">{pick_val}</b> | Wager: <b>{wager_amt} 🪙</b>
                        </div>
                    """,
              unsafe_allow_html=True,
          )
          share_lines.append(f"Q{q_num}: {pick_val} ({wager_amt} tokens)")

        td_name = curr_user_td[0]["player_name"] if curr_user_td else "None"
        st.markdown(
            f"""
                    <div class="summary-box" style="border-left-color: #38bdf8 !important;">
                        <b>🏈 Touchdown Scorer Bonus Pick:</b><br>
                        • Player: <b style="color:#38bdf8;">{td_name}</b>
                    </div>
                """,
            unsafe_allow_html=True,
        )
        share_lines.append(f"TD Scorer Pick: {td_name}")

        st.write("")
        st.subheader("📋 Group Chat Share Text")
        share_text_block = "\n".join(share_lines)
        st.code(share_text_block, language="markdown")
        st.success(
            "Copy the text box above to share your picks directly into WhatsApp"
            " or group chat!"
        )

    graded_q_badge = (
        supabase.table("weekly_questions")
        .select("week_number")
        .neq("week_number", 999)
        .neq("week_number", 998)
        .neq("week_number", 997)
        .neq("week_number", 96)
        .neq("winning_answer", "Pending")
        .neq("winning_answer", "LOCKED")
        .order("week_number", desc=True)
        .execute()
        .data
    )

    if graded_q_badge:
      latest_mvp_week = graded_q_badge[0]["week_number"]
      mvp_bets = (
          supabase.table("user_bets")
          .select("*, weekly_questions(winning_answer)")
          .eq("week_number", latest_mvp_week)
          .execute()
          .data
      )
      mvp_tds = (
          supabase.table("touchdown_picks")
          .select("*")
          .eq("week_number", latest_mvp_week)
          .eq("is_correct", True)
          .execute()
          .data
      )

      user_weekly_net = {}
      for b in mvp_bets:
        u = b["user_id"]
        w_ans = b.get("weekly_questions", {}).get("winning_answer")
        if u not in user_weekly_net:
          user_weekly_net[u] = 0
        if w_ans in ["Yes", "No"]:
          if b["pick"] == w_ans:
            user_weekly_net[u] += b["wager_amount"]
          else:
            user_weekly_net[u] -= b["wager_amount"]
      for td in mvp_tds:
        u = td["user_id"]
        user_weekly_net[u] = user_weekly_net.get(u, 0) + 5

      if user_weekly_net and max(user_weekly_net.values(), default=-1) > 0:
        top_mvp_id = max(user_weekly_net, key=user_weekly_net.get)
        top_mvp_tokens = user_weekly_net[top_mvp_id]
        mvp_profile = (
            supabase.table("profiles")
            .select("full_name, avatar_emoji, favorite_team")
            .eq("id", top_mvp_id)
            .single()
            .execute()
            .data
        )

        if mvp_profile:
          st.markdown(
              f"""
                        <div class="mvp-banner">
                            <div style="font-size: 16px; letter-spacing: 2px; text-transform: uppercase; color: #f3e8ff;">🔥 Week {latest_mvp_week} League MVP 🔥</div>
                            <div style="font-size: 36px; font-weight: 900; margin: 5px 0; color: #ffffff;">{mvp_profile.get('avatar_emoji', '🏈')} {mvp_profile['full_name']}</div>
                            <div style="font-size: 16px; color: #d8b4fe;">Dominated the slate with <b>+{top_mvp_tokens} Net Tokens</b>! 🚀</div>
                        </div>
                    """,
              unsafe_allow_html=True,
          )

    if available_weeks:
      current_active_week = available_weeks[-1]
      st.divider()
      st.subheader(f"📊 Week {current_active_week} Community Trends & Action")
      st.caption(
          "A snapshot of how the league is leaning on this week's active"
          " matchups."
      )

      live_all_bets = (
          supabase.table("user_bets")
          .select("question_id, pick, wager_amount, weekly_questions(question_text)")
          .eq("week_number", current_active_week)
          .execute()
          .data
      )
      if live_all_bets:
        q_stats = {}
        for b in live_all_bets:
          q_text = b.get("weekly_questions", {}).get("question_text", "Question")
          clean_q = (
              q_text.split(" | MATCHUP: ")[0]
              if " | MATCHUP: " in q_text
              else q_text
          )
          if clean_q not in q_stats:
            q_stats[clean_q] = {"Yes": 0, "No": 0, "TotalWager": 0, "Votes": 0}
          q_stats[clean_q][b["pick"]] += 1
          q_stats[clean_q]["TotalWager"] += b["wager_amount"]
          q_stats[clean_q]["Votes"] += 1

        trend_list = []
        for q_name, data in q_stats.items():
          yes_v = data["Yes"]
          no_v = data["No"]
          tot = data["Votes"]
          if tot > 0:
            yes_pct = int((yes_v / tot) * 100)
            no_pct = 100 - yes_pct
            majority_pick = "YES" if yes_pct >= 50 else "NO"
            majority_pct = max(yes_pct, no_pct)
            trend_list.append({
                "question": q_name,
                "consensus": f"{majority_pct}% {majority_pick}",
                "total_wagered": data["TotalWager"],
                "votes": tot,
            })

        if trend_list:
          trend_df = (
              pd.DataFrame(trend_list)
              .sort_values(by="total_wagered", ascending=False)
              .head(3)
          )
          for _, row in trend_df.iterrows():
            st.markdown(
                f"""
                            <div class="summary-box">
                                <b>🔥 Heaviest Action: {row['question']}</b><br>
                                • <b>League Consensus:</b> {row['consensus']} ({row['votes']} total player bets)<br>
                                • <b>Total Tokens Wagered on Matchup:</b> {row['total_wagered']} 🪙
                            </div>
                        """,
                unsafe_allow_html=True,
            )
        else:
          st.info(
              "No bets placed for the current week yet. Be the first to lock in"
              " your picks!"
          )
      else:
        st.info(
            "No bets placed for the current week yet. Be the first to lock in"
            " your picks!"
        )

    st.divider()
    st.subheader("📊 Last Week's Performance Summary")

    all_graded_weeks_meta = get_cached_all_weekly_questions_meta()
    graded_weeks_set = set()
    closed_markers = (
        supabase.table("weekly_questions")
        .select("week_number")
        .eq("question_number", 96)
        .eq("winning_answer", "CLOSED")
        .execute()
        .data
    )
    if closed_markers:
      for cm in closed_markers:
        graded_weeks_set.add(cm["week_number"])

    if all_graded_weeks_meta:
      w_map = {}
      for q in all_graded_weeks_meta:
        w_num = q["week_number"]
        ans = q["winning_answer"]
        if w_num not in w_map:
          w_map[w_num] = []
        if q.get("question_number", 0) <= 10:
          w_map[w_num].append(ans)
      for w_num, ans_list in w_map.items():
        if ans_list and all(a in ["Yes", "No"] for a in ans_list):
          graded_weeks_set.add(w_num)

    graded_weeks_list = sorted(list(graded_weeks_set))

    if not graded_weeks_list:
      st.info(
          "No weeks have been graded yet. Place your bets for Week 1 to get"
          " started!"
      )
    else:
      latest_graded_week = graded_weeks_list[-1]
      lw_bets = (
          supabase.table("user_bets")
          .select("*, weekly_questions(winning_answer)")
          .eq("user_id", user_id)
          .eq("week_number", latest_graded_week)
          .execute()
          .data
      )
      lw_td = (
          supabase.table("touchdown_picks")
          .select("*")
          .eq("user_id", user_id)
          .eq("week_number", latest_graded_week)
          .execute()
          .data
      )

      if not lw_bets and not lw_td:
        st.warning(
            f"You did not submit any bets or touchdown picks for Week"
            f" {latest_graded_week}."
        )
      else:
        bet_gains = 0
        bet_losses = 0
        correct_count = 0
        total_bets_placed = len(lw_bets)

        for b in lw_bets:
          w_ans = b.get("weekly_questions", {}).get("winning_answer")
          if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
              bet_gains += b["wager_amount"]
              correct_count += 1
            else:
              bet_losses += b["wager_amount"]

        td_record = lw_td[0] if lw_td else None

        if td_record is None or td_record.get("is_correct") is None:
          td_is_graded = False
          td_bonus = 0
          td_display_status = "⏳ Pending (Awaiting Admin Grading)"
        else:
          td_is_graded = True
          is_c = td_record.get("is_correct")
          if str(is_c).lower() == "true":
            td_bonus = 5
            td_display_status = "✅ Correct (+5 Tokens)"
          else:
            td_bonus = 0
            td_display_status = "❌ Incorrect (Missed)"

        td_player = td_record["player_name"] if td_record else "None"
        net_total = bet_gains - bet_losses + td_bonus

        celeb_key = f"celebrated_week_{latest_graded_week}_{user_id}"
        if net_total > 0 and not st.session_state.get(celeb_key, False):
          st.balloons()
          st.session_state[celeb_key] = True

        st.markdown(f"### Week {latest_graded_week} Results")

        col1, col2, col3 = st.columns(3)
        with col1:
          st.metric(
              "Net Tokens Earned",
              f"{'+' if net_total >= 0 else ''}{net_total} 🪙",
          )
        with col2:
          st.metric("Questions Correct", f"{correct_count} / {total_bets_placed}")
        with col3:
          if not td_is_graded:
            st.metric("TD Scorer Bonus", "Pending ⏳")
          else:
            st.metric(
                "TD Scorer Bonus",
                f"+{td_bonus} 🪙" if td_bonus > 0 else "0 🪙",
            )

        st.markdown(
            f"""
                <div class="summary-box">
                    <b>Week {latest_graded_week} Breakdown:</b><br>
                    • <b>Question Wins:</b> +{bet_gains} Tokens<br>
                    • <b>Question Losses:</b> -{bet_losses} Tokens<br>
                    • <b>Touchdown Scorer Pick:</b> '{td_player}' ({td_display_status})
                </div>
                """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("📊 Token History Graph")

    history_bets_all = (
        supabase.table("user_bets")
        .select("week_number, wager_amount, pick, weekly_questions(winning_answer)")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    all_td_history = (
        supabase.table("touchdown_picks")
        .select("week_number, is_correct")
        .eq("user_id", user_id)
        .eq("is_correct", True)
        .execute()
        .data
    )

    td_wins_map = {td["week_number"]: 5 for td in all_td_history}

    if history_bets_all or td_wins_map:
      week_tokens = {0: 10}
      curr_tokens = 10
      all_weeks_involved = sorted(
          list(
              set(
                  [b["week_number"] for b in history_bets_all]
                  + list(td_wins_map.keys())
              )
          )
      )

      for w in all_weeks_involved:
        w_bets = [b for b in history_bets_all if b["week_number"] == w]
        for b in w_bets:
          w_ans = b.get("weekly_questions", {}).get("winning_answer")
          if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
              curr_tokens += b["wager_amount"]
            else:
              curr_tokens -= b["wager_amount"]
        if w in td_wins_map:
          curr_tokens += 5

        week_tokens[w] = max(0, curr_tokens)

      chart_weeks = list(week_tokens.keys())
      chart_vals = list(week_tokens.values())

      def hex_to_rgba(hex_str, alpha=0.25):
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 3:
          hex_str = "".join([c * 2 for c in hex_str])
        try:
          r, g, b = (
              int(hex_str[0:2], 16),
              int(hex_str[2:4], 16),
              int(hex_str[4:6], 16),
          )
          return f"rgba({r}, {g}, {b}, {alpha})"
        except Exception:
          return f"rgba(251, 191, 36, {alpha})"

      fill_rgba_color = hex_to_rgba(user_team_color, 0.25)

      fig = go.Figure()
      fig.add_trace(
          go.Scatter(
              x=[f"Week {w}" if w > 0 else "Start" for w in chart_weeks],
              y=chart_vals,
              mode="lines+markers",
              name="Token Bank",
              line=dict(color=user_team_color, width=4, shape="spline"),
              marker=dict(
                  size=10, color=user_team_color, line=dict(color="#ffffff", width=2)
              ),
              fill="tozeroy",
              fillcolor=fill_rgba_color,
              hovertemplate=(
                  "<b>%{x}</b><br>Token Balance: %{y} 🪙<extra></extra>"
              ),
          )
      )

      fig.update_layout(
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(15, 23, 42, 0.75)",
          margin=dict(l=10, r=10, t=10, b=10),
          xaxis=dict(
              showgrid=True,
              gridcolor="rgba(255,255,255,0.08)",
              tickfont=dict(color="#cbd5e1", family="Inter", size=12),
              zeroline=False,
          ),
          yaxis=dict(
              showgrid=True,
              gridcolor="rgba(255,255,255,0.08)",
              tickfont=dict(color="#cbd5e1", family="Inter", size=12),
              zeroline=False,
          ),
          hoverlabel=dict(
              bgcolor="#0f172a", font_color="#ffffff", font_family="Inter"
          ),
      )

      st.plotly_chart(fig, use_container_width=True)
    else:
      st.info("No token history data available yet.")

  # ------------------------------------------
  # TAB 1: PROFILE & TROPHY CABINET
  # ------------------------------------------
  with tab_profile:
    st.header("👤 Profile & Customization Hub")
    st.caption(
        "Personalize your display avatar, title nametag, border style, avatar"
        " color, favorite player, favorite team, and featured badges!"
    )

    curr_team = profile.get("favorite_team", "🏈 Free Agent / Neutral")
    team_index = NFL_TEAMS.index(curr_team) if curr_team in NFL_TEAMS else 0

    new_team = st.selectbox("Favorite NFL Team", NFL_TEAMS, index=team_index)
    selected_team_data = NFL_TEAM_DATA.get(
        new_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
    )

    col_logo, col_info = st.columns([1, 4])
    with col_logo:
      st.image(selected_team_data["logo"], width=75)
    with col_info:
      st.markdown(f"### {new_team}")

    user_badges_for_titles = sync_and_get_user_badges(user_id)
    unlocked_title_options = []
    locked_title_info = []

    for title_name, info in AVAILABLE_TITLES.items():
      if info["badge"] is None or info["badge"] in user_badges_for_titles:
        unlocked_title_options.append(title_name)
      else:
        locked_title_info.append((title_name, info["req"]))

    curr_selected_title = profile.get("selected_title", "🏈 Gridiron Contender")
    if curr_selected_title not in unlocked_title_options:
      curr_selected_title = (
          unlocked_title_options[0]
          if unlocked_title_options
          else "🏈 Gridiron Contender"
      )
    title_index = (
        unlocked_title_options.index(curr_selected_title)
        if curr_selected_title in unlocked_title_options
        else 0
    )

    with st.form("profile_customization_form"):
      new_display_name = st.text_input(
          "Display Name", value=profile.get("full_name", "")
      )

      col_t1, col_t2 = st.columns(2)
      with col_t1:
        new_title = st.selectbox(
            "Active Nametag Title",
            unlocked_title_options,
            index=title_index,
            help="Select from your unlocked prestigious titles!",
        )
      with col_t2:
        curr_avatar = profile.get("avatar_emoji", "🏈")
        avatar_index = (
            AVATAR_OPTIONS.index(curr_avatar)
            if curr_avatar in AVATAR_OPTIONS
            else 0
        )
        new_avatar = st.selectbox(
            "Avatar Emoji", AVATAR_OPTIONS, index=avatar_index
        )

      col_av2, col_av3 = st.columns(2)
      with col_av2:
        curr_border = profile.get("avatar_border", "solid")
        border_keys = list(BORDER_STYLE_OPTIONS.keys())
        border_vals = list(BORDER_STYLE_OPTIONS.values())
        border_index = (
            border_vals.index(curr_border) if curr_border in border_vals else 0
        )
        selected_border_label = st.selectbox(
            "Avatar Border", border_keys, index=border_index
        )
        new_border = BORDER_STYLE_OPTIONS[selected_border_label]
      with col_av3:
        curr_av_color = profile.get("avatar_color", "#1e3a8a")
        new_av_color = st.color_picker(
            "Avatar Box Color", value=curr_av_color
        )

      new_fav_player = st.text_input(
          "Favorite NFL Player", value=profile.get("favorite_player", "")
      )
      new_bio = st.text_input(
          "Profile Catchphrase / Bio (max 100 chars)",
          value=profile.get("bio", "Ready for Kickoff!"),
          max_chars=100,
      )

      save_profile = st.form_submit_button("Save Profile Settings 💾", type="primary")

      if save_profile:
        if not new_display_name.strip():
          st.error("Display Name cannot be blank.")
        elif (
            contains_profanity(new_display_name)
            or contains_profanity(new_fav_player)
            or contains_profanity(new_bio)
        ):
          st.error(
              "⚠️ Your profile input contains restricted language. Please choose"
              " appropriate wording."
          )
        else:
          supabase.table("profiles").update({
              "full_name": new_display_name.strip(),
              "favorite_team": new_team,
              "selected_title": new_title,
              "avatar_emoji": new_avatar,
              "avatar_border": new_border,
              "avatar_color": new_av_color,
              "favorite_player": new_fav_player.strip(),
              "bio": new_bio.strip(),
          }).eq("id", user_id).execute()
          st.success("Profile updated successfully!")
          st.rerun()

    if locked_title_info:
      st.write("")
      with st.expander("🔒 Locked Nametag Titles & How to Unlock Them"):
        st.caption(
            "Complete achievements and unlock badges to add these titles to your"
            " selectable collection!"
        )
        for l_title, l_req in locked_title_info:
          st.markdown(f"• **{l_title}** — *Requirement:* {l_req}")

    st.divider()
    st.subheader("⭐ Featured Badge Showcase")
    st.caption(
        "Choose up to 3 unlocked badges to showcase on your leaderboard card."
    )

    unlocked_badges = sync_and_get_user_badges(user_id)
    current_featured = profile.get("featured_badges", [])
    if not isinstance(current_featured, list):
      current_featured = []
    valid_current_featured = [b for b in current_featured if b in unlocked_badges]

    with st.form("featured_badges_form"):
      selected_featured = st.multiselect(
          "Select up to 3 Badges to Showcase",
          options=unlocked_badges,
          default=valid_current_featured,
          max_selections=3,
          help=(
              "Choose your favorite trophies to display proudly on the"
              " leaderboard!"
          ),
      )

      save_featured_btn = st.form_submit_button(
          "Save Featured Badges 🌟", type="primary"
      )

      if save_featured_btn:
        supabase.table("profiles").update(
            {"featured_badges": selected_featured}
        ).eq("id", user_id).execute()
        st.success("Featured badges updated successfully!")
        st.rerun()

    st.divider()
    st.subheader("🏆 Virtual Trophy Cabinet")
    st.caption("Inspect badge showcases across any league member.")

    all_league_profiles = get_cached_profiles()
    user_name_map = {p["full_name"]: p for p in all_league_profiles}

    default_profile_name = profile.get(
        "full_name", list(user_name_map.keys())[0] if user_name_map else ""
    )
    default_index = (
        list(user_name_map.keys()).index(default_profile_name)
        if default_profile_name in user_name_map
        else 0
    )

    st.markdown("**Select Player Trophy Showcase:**")
    selected_player_name = st.selectbox(
        "Select Player Trophy Showcase",
        list(user_name_map.keys()),
        index=default_index,
        key="trophy_player_select",
        label_visibility="collapsed",
    )
    selected_player = user_name_map[selected_player_name]

    if selected_player["id"] == user_id:
      selected_badges = sync_and_get_user_badges(user_id)
    else:
      selected_badges = selected_player.get("unlocked_badges") or []

    selected_team_info = NFL_TEAM_DATA.get(
        selected_player.get("favorite_team"),
        NFL_TEAM_DATA["🏈 Free Agent / Neutral"],
    )

    unlocked_count = len(selected_badges)
    total_badges_count = len(MASTER_BADGES)
    progress_ratio = unlocked_count / total_badges_count
    progress_pct = int(progress_ratio * 100)

    col_t_logo, col_t_info = st.columns([1, 4])
    with col_t_logo:
      st.image(selected_team_info["logo"], width=70)
    with col_t_info:
      st.markdown(
          f"### {selected_player.get('avatar_emoji', '🏈')}"
          f" {selected_player['full_name']}'s Showcase"
      )
      st.markdown(
          f"**Unlocked:** `{unlocked_count}` / `{total_badges_count}` Badges"
      )

    st.progress(
        progress_ratio, text=f"**Cabinet Completion:** `{progress_pct}%` Unlocked"
    )
    st.write("")

    t_col1, t_col2 = st.columns(2)
    for idx, (b_name, b_desc) in enumerate(MASTER_BADGES.items()):
      is_unlocked = b_name in selected_badges
      target_col = t_col1 if idx % 2 == 0 else t_col2

      with target_col:
        if is_unlocked:
          st.markdown(
              f"""
                        <div class="trophy-card-unlocked">
                            <b>{b_name}</b> <span style="color:#fbbf24; font-weight:bold;">(UNLOCKED)</span><br>
                            <small style="color:#cbd5e1;">{b_desc}</small>
                        </div>
                    """,
              unsafe_allow_html=True,
          )
        else:
          st.markdown(
              f"""
                        <div class="trophy-card-locked">
                            <b>🔒 {b_name}</b><br>
                            <small>{b_desc}</small>
                        </div>
                    """,
              unsafe_allow_html=True,
          )

  # ------------------------------------------
  # TAB 2: RULES & INFO
  # ------------------------------------------
  with tab_rules:
    st.markdown("## 📖 Rules & Information Hub")
    st.caption("Everything you need to know about dominating Touchdown Tokens.")
    st.write("")

    st.markdown(
        f"""
            <div class="rule-card">
                <div class="rule-step-num">01 / THE CORE PREMISE</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">10 Scenarios. Cumulative Tokens. High Stakes.</div>
                <p style="color: #cbd5e1; line-height: 1.6; margin: 0;">
                    Each week brings 10 custom NFL scenarios. Every player starts with 10 tokens. When you win a bet, your wagered tokens double! Lose a bet, and those wagered tokens are lost. Your token bank is cumulative across the entire season—build a massive lead or claw your way back from zero.
                </p>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
            <div class="rule-card">
                <div class="rule-step-num">02 / TOUCHDOWN SCORER BONUS</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">The Free Weekly Scorer Pick (+5 Tokens)</div>
                <p style="color: #cbd5e1; line-height: 1.6; margin: 0;">
                    At the bottom of your weekly slate, you can name 1 player to score a touchdown. If your chosen player rushes or receives a touchdown, you instantly pocket <b style="color: {user_team_color};">+5 bonus tokens</b> for the next week! <i>Note: Passing touchdowns do not count.</i>
                </p>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
            <div class="rule-card">
                <div class="rule-step-num">03 / SCHEDULE & CUTOFFS</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Sunday & Monday Slates Only</div>
                <p style="color: #cbd5e1; line-height: 1.6; margin: 0;">
                    All scenarios feature Sunday or Monday games (no Thursday night fixtures). Submissions automatically lock down precisely <b style="color: #38bdf8;">15 minutes before the first Sunday kickoff</b>. Make sure your lock-ins are saved before time expires!
                </p>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
            <div class="rule-card">
                <div class="rule-step-num">04 / IMPORTANT LEAGUE POLICIES</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Fair Play, Overrides & Inactive Scratches</div>
                <ul style="color: #cbd5e1; padding-left: 20px; line-height: 1.6; margin: 0;">
                    <li><b>Submissions & Overrides:</b> You can update your picks and wagers as many times as you like before the kickoff deadline. <b>Your final submit will be your real one and it will completely override your previous picks!</b></li>
                    <li><b>Submitting with 0 Wagers:</b> Even if you don't want to risk any tokens on a specific question, you can still submit your Yes/No answer with a <b>0 token wager</b> to test your predictions and see how you would have performed!</li>
                    <li><b>Late Scratches:</b> If a specific player mentioned in a scenario is ruled out before kickoff, bets on that scenario are fully refunded.</li>
                    <li><b>Missed Weeks:</b> Taking a week off is totally fine, though consistent consecutive absences may incur point deductions.</li>
                    <li><b>One Choice Per Question:</b> Lock in either Yes or No per matchup.</li>
                </ul>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
            <div class="rule-card" style="border-top-color: #38bdf8;">
                <div class="rule-step-num" style="color: #38bdf8;">📱 PRO TIP / MOBILE ACCESS</div>
                <div style="font-size: 18px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Add Touchdown Tokens to Your Phone Home Screen</div>
                <p style="color: #cbd5e1; line-height: 1.6; margin-bottom: 12px;">
                    Treat this app like a native mobile app for instant access on game days:
                </p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div style="background: rgba(15,23,42,0.6); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);">
                        <b style="color: #38bdf8;">🍎 iPhone (Safari):</b><br>
                        Tap the <i>Share Button</i> at the bottom → Select <b>'Add to Home Screen'</b>.
                    </div>
                    <div style="background: rgba(15,23,42,0.6); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);">
                        <b style="color: #38bdf8;">🤖 Android (Chrome):</b><br>
                        Tap the <i>3 Dots Menu</i> at top right → Select <b>'Install App'</b> or <b>'Add to Home Screen'</b>.
                    </div>
                </div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    with st.expander("❓ Frequently Asked Questions (FAQ)"):
      st.markdown("""
                ### 📋 General & Gameplay FAQs

                **Q: What happens if an NFL game is postponed or canceled?**  
                *A:* Any scenario connected to a game that is postponed or canceled is automatically voided, and all tokens wagered on that scenario are fully refunded to your bank.

                **Q: Can I submit my picks without wagering any tokens?**  
                *A:* Yes! Even if you don't want to risk any tokens on a question, you can lock in your Yes/No pick with a **0 token wager**. This lets you participate, test your predictions, and track how well you would have done without risking your bank balance.

                **Q: Can I change my picks after submitting them?**  
                *A:* Yes, you can submit new picks and wagers as many times as you like before the kickoff lockout. **Your final submit will be your real one and it will completely override your previous picks.**

                **Q: How does the Touchdown Scorer bonus work?**  
                *A:* You can name any player to score a rushing or receiving touchdown. Passing touchdowns do not count. If your selected player scores, you pocket **+5 bonus tokens** for the following week!

                **Q: What is a "Nemesis" on the leaderboard?**  
                *A:* Your Nemesis is the player in your selected league whom you disagreed with the most on weekly bets where they ended up winning points at your expense!

                **Q: How do I unlock prestigious nametag titles?**  
                *A:* Titles like *The Oracle*, *Token Tycoon*, and *Gridiron Prophet* unlock automatically as you achieve milestone records or unlock specific badges in your Virtual Trophy Cabinet. Once unlocked, you can select them from your **Profile** tab!

                **Q: What happens if my token balance drops to 0?**  
                *A:* Don't worry! Reaching 0 tokens unlocks the *Down Bad* badge and title, but you can always bounce back in future weeks through the Touchdown Scorer bonus or special league events.
            """)

  # ------------------------------------------
  # TAB 3: PLACE BETS
  # ------------------------------------------
  with tab_bet:
    st.header("Weekly Predictions & Wagers")
    st.link_button(
        "🏈 View NFL Scores, Lines & Fixtures ↗️",
        "https://www.espn.com/nfl/schedule",
    )
    st.caption(
        "Check real-time odds and matchups on ESPN before locking in your picks"
        " below."
    )
    st.write("")

    if not available_weeks:
      st.info(
          "No active questions available yet. Check back soon when the Admin"
          " posts Week 1!"
      )
    else:
      active_unscored_weeks = []
      for w in available_weeks:
        week_status_row = (
            supabase.table("weekly_questions")
            .select("winning_answer")
            .eq("week_number", w)
            .eq("question_number", 96)
            .execute()
            .data
        )
        is_closed = (
            week_status_row and week_status_row[0]["winning_answer"] == "CLOSED"
        )

        if not is_closed:
          w_qs_check = (
              supabase.table("weekly_questions")
              .select("winning_answer")
              .eq("week_number", w)
              .neq("week_number", 999)
              .neq("week_number", 998)
              .neq("week_number", 997)
              .neq("week_number", 96)
              .execute()
              .data
          )
          if w_qs_check and all(
              q["winning_answer"] in ["Yes", "No"] for q in w_qs_check
          ):
            is_closed = True

        if not is_closed:
          active_unscored_weeks.append(w)

      if not active_unscored_weeks:
        st.info(
            "🎉 All currently available weeks have been graded and closed!"
            " Check back when the Admin posts a new active week."
        )
      else:
        selected_week = st.selectbox(
            "Select Week:",
            active_unscored_weeks,
            index=len(active_unscored_weeks) - 1,
        )

        q_res = get_cached_weekly_questions(selected_week)
        questions = q_res

        is_locked = False
        lock_time_row = [
            q
            for q in questions
            if q.get("winning_answer", "").startswith("LOCKTIME:")
        ]

        if lock_time_row:
          raw_lock_str = lock_time_row[0]["winning_answer"].replace(
              "LOCKTIME:", ""
          )
          try:
            lock_dt = datetime.fromisoformat(raw_lock_str).replace(
                tzinfo=timezone.utc
            )
            now_dt = datetime.now(timezone.utc)
            time_diff = lock_dt - now_dt

            total_seconds_left = int(time_diff.total_seconds())
            if total_seconds_left <= 0:
              is_locked = True
              st.error(
                  "🔒 Entries for this week are locked! Kickoff deadline has"
                  " passed."
              )
            else:
              days, remainder = divmod(total_seconds_left, 86400)
              hours, remainder = divmod(remainder, 3600)
              minutes, seconds = divmod(remainder, 60)

              time_display_str = (
                  f"{days}d {hours}h {minutes}m {seconds}s"
                  if days > 0
                  else f"{hours}h {minutes}m {seconds}s"
              )

              st.markdown(
                  f"""
                                <div class="timer-card">
                                    ⏳ <b>KICKOFF LOCKOUT COUNTDOWN:</b> <span style="font-size:20px; font-weight:bold; color:{user_team_color};">{time_display_str} remaining</span>
                                </div>
                            """,
                  unsafe_allow_html=True,
              )
          except Exception:
            pass

        if any(q.get("winning_answer") == "LOCKED" for q in questions):
          is_locked = True
          st.error(
              "🔒 Entries for this week have been manually locked by the Admin."
          )

        if not questions:
          st.info("No questions found for this week.")
        else:
          true_global_tokens_bet = get_true_global_token_balance(user_id)
          if not is_locked and true_global_tokens_bet > 0:
            col_rand_sp1, col_rand_btn = st.columns([3, 1])
            with col_rand_btn:
              if st.button(
                  "🎲 Feeling Lucky (Randomize)",
                  help=(
                      "Randomly distributes your available tokens and picks"
                      " across the questions!"
                  ),
              ):
                with st.spinner(
                    "🎲 Simulating lucky picks and distributing tokens..."
                ):
                  real_q_items = [
                      q
                      for q in questions
                      if not q.get("winning_answer", "").startswith("LOCKTIME:")
                  ]
                  if real_q_items:
                    remaining_tokens = true_global_tokens_bet
                    supabase.table("user_bets").delete().eq(
                        "user_id", user_id
                    ).eq("week_number", selected_week).execute()

                    token_allocations = {q["id"]: 0 for q in real_q_items}
                    for _ in range(remaining_tokens):
                      chosen_q = random.choice(real_q_items)
                      token_allocations[chosen_q["id"]] += 1

                    for q_item in real_q_items:
                      random_pick = random.choice(["Yes", "No"])
                      w_amt = token_allocations[q_item["id"]]

                      supabase.table("user_bets").insert({
                          "user_id": user_id,
                          "user_name": profile["full_name"],
                          "week_number": selected_week,
                          "question_id": q_item["id"],
                          "pick": random_pick,
                          "wager_amount": w_amt,
                      }).execute()

                    st.cache_data.clear()
                    st.session_state.form_refresh += 1
                    st.success(
                        "🎲 Random bets generated and populated successfully!"
                    )
                    st.rerun()

          all_week_bets = (
              supabase.table("user_bets")
              .select("question_id, pick, wager_amount")
              .eq("user_id", user_id)
              .eq("week_number", selected_week)
              .execute()
              .data
          )
          existing_bets_map = {b["question_id"]: b for b in all_week_bets}

          existing_td = (
              supabase.table("touchdown_picks")
              .select("player_name")
              .eq("user_id", user_id)
              .eq("week_number", selected_week)
              .execute()
              .data
          )
          default_td = existing_td[0]["player_name"] if existing_td else ""

          with st.form("weekly_bet_form"):
            wagers = {}
            picks = {}

            st.markdown("### 10 Weekly Questions")
            st.caption(
                "Select your pick (Yes/No) and assign your token wagers smoothly"
                " without interruptions. Hit submit at the bottom when ready!"
            )

            for q in questions:
              if q.get("winning_answer", "").startswith("LOCKTIME:"):
                continue

              full_q_text = q["question_text"]
              away_team_name = "🏈 Free Agent / Neutral"
              home_team_name = "🏈 Free Agent / Neutral"
              prompt_text = full_q_text

              if " | MATCHUP: " in full_q_text:
                parts = full_q_text.split(" | MATCHUP: ")
                prompt_text = parts[0]
                matchup_str = parts[1]
                if " @ " in matchup_str:
                  teams_split = matchup_str.split(" @ ")
                  away_team_name = teams_split[0]
                  home_team_name = teams_split[1]

              away_info = NFL_TEAM_DATA.get(
                  away_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
              )
              home_info = NFL_TEAM_DATA.get(
                  home_team_name, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
              )

              prev_bet = existing_bets_map.get(q["id"], {})
              default_pick_val = prev_bet.get("pick", "Yes")
              default_wager_val = prev_bet.get("wager_amount", 0)

              pick_index = 0 if default_pick_val == "Yes" else 1

              with st.expander(
                  f"Q{q['question_number']}: {prompt_text[:45]}..."
                  f" ({away_team_name} @ {home_team_name})",
                  expanded=True,
              ):
                col_away_logo, col_matchup_txt, col_home_logo = st.columns(
                    [1, 4, 1]
                )
                with col_away_logo:
                  st.image(away_info["logo"], width=35)
                with col_matchup_txt:
                  st.markdown(
                      f"""
                                        <div style="text-align:center; padding-top:2px;">
                                            <span class="matchup-team-title" style="font-size:20px;">{away_team_name}</span>
                                            <span style="color:#cbd5e1; font-weight:bold; margin: 0 6px;">@</span>
                                            <span class="matchup-team-title" style="font-size:20px;">{home_team_name}</span>
                                        </div>
                                    """,
                      unsafe_allow_html=True,
                  )
                with col_home_logo:
                  st.image(home_info["logo"], width=35)

                st.markdown(f"**Question: {prompt_text}**")

                col_pick, col_wager = st.columns([1, 1])
                with col_pick:
                  picks[q["id"]] = st.radio(
                      f"Pick Q{q['question_number']}",
                      ["Yes", "No"],
                      index=pick_index,
                      key=(
                          f"pick_w{selected_week}_{q['id']}_{st.session_state.form_refresh}"
                      ),
                      horizontal=True,
                      disabled=is_locked,
                  )
                with col_wager:
                  wagers[q["id"]] = st.number_input(
                      f"Wager Q{q['question_number']}",
                      min_value=0,
                      max_value=true_global_tokens_bet,
                      value=default_wager_val,
                      key=(
                          f"wager_w{selected_week}_{q['id']}_{st.session_state.form_refresh}"
                      ),
                      disabled=is_locked,
                  )

            st.markdown("### 🏈 Bonus Touchdown Scorer Pick")
            st.caption(
                "Name 1 player to score a TD this week (Rushing/Receiving"
                " only!). Correct pick = Bonus Tokens!"
            )

            td_pick = st.text_input(
                "Player Name (e.g., Patrick Mahomes)",
                value=default_td,
                key=(
                    f"td_scorer_w{selected_week}_{st.session_state.form_refresh}"
                ),
                disabled=is_locked,
            )

            total_wagered = sum(wagers.values())
            max_available = max(1, true_global_tokens_bet)
            progress_val = min(1.0, total_wagered / max_available)
            pct_str = int(progress_val * 100)

            if total_wagered > true_global_tokens_bet:
              st.error(
                  f"⚠️ Over-wagered! You have allocated {total_wagered} tokens"
                  f" but only have {true_global_tokens_bet} available."
              )
            else:
              st.progress(
                  progress_val,
                  text=(
                      f"**Tokens Allocated:** `{total_wagered}` /"
                      f" `{true_global_tokens_bet}` Tokens ({pct_str}%)"
                  ),
              )

            st.caption(
                "💡 *Tip: Remember that even if you don't want to risk tokens on"
                " a question, you can set the wager to 0 tokens to submit your"
                " answer and test how you would have done!*"
            )

            col_sub1, col_sub2 = st.columns([2, 1])
            with col_sub1:
              submit_bet = st.form_submit_button(
                  "Submit Weekly Bets 🚀", type="primary", disabled=is_locked
              )
            with col_sub2:
              clear_bet = st.form_submit_button(
                  "Clear Bet Choices 🗑️", disabled=is_locked
              )

            if clear_bet and not is_locked:
              supabase.table("user_bets").delete().eq(
                  "user_id", user_id
              ).eq("week_number", selected_week).execute()
              supabase.table("touchdown_picks").delete().eq(
                  "user_id", user_id
              ).eq("week_number", selected_week).execute()
              st.session_state.form_refresh += 1
              st.success("Your bet choices for this week have been cleared!")
              st.rerun()

            if submit_bet and not is_locked:
              if contains_profanity(td_pick):
                st.error(
                    "⚠️ Your Touchdown Scorer player pick contains restricted"
                    " language. Please choose a valid player name."
                )
              elif total_wagered > true_global_tokens_bet:
                st.error(
                    f"Cannot wager {total_wagered} tokens! You only have"
                    f" {true_global_tokens_bet} tokens available."
                )
              else:
                for q_id, pick_val in picks.items():
                  w_amt = wagers[q_id]
                  supabase.table("user_bets").delete().eq(
                      "user_id", user_id
                  ).eq("question_id", q_id).execute()
                  supabase.table("user_bets").insert({
                      "user_id": user_id,
                      "user_name": profile["full_name"],
                      "week_number": selected_week,
                      "question_id": q_id,
                      "pick": pick_val,
                      "wager_amount": w_amt,
                  }).execute()

                if td_pick:
                  supabase.table("touchdown_picks").delete().eq(
                      "user_id", user_id
                  ).eq("week_number", selected_week).execute()
                  supabase.table("touchdown_picks").insert({
                      "user_id": user_id,
                      "week_number": selected_week,
                      "player_name": td_pick,
                      "is_correct": None,
                  }).execute()

                st.balloons()
                st.success(
                    "Your bets and touchdown pick have been successfully locked"
                    " in!"
                )

  # ------------------------------------------
  # TAB 4: MY HISTORY & SIDE-BY-SIDE COMPARISON
  # ------------------------------------------
  with tab_history:
    st.header("📜 Your Past Bets & Results")
    st.caption(
        "Review your historical predictions, weekly outcomes, and track your"
        " performance over time."
    )

    all_graded_weeks_res = get_cached_all_weekly_questions_meta()
    graded_weeks_set = set()

    closed_markers = (
        supabase.table("weekly_questions")
        .select("week_number")
        .eq("question_number", 96)
        .eq("winning_answer", "CLOSED")
        .execute()
        .data
    )
    if closed_markers:
      for cm in closed_markers:
        graded_weeks_set.add(cm["week_number"])

    if all_graded_weeks_res:
      week_ans_map = {}
      for q in all_graded_weeks_res:
        w_num = q["week_number"]
        ans = q["winning_answer"]
        if w_num not in week_ans_map:
          week_ans_map[w_num] = []
        if q.get("question_number", 0) <= 10:
          week_ans_map[w_num].append(ans)

      for w_num, ans_list in week_ans_map.items():
        if ans_list and all(a in ["Yes", "No"] for a in ans_list):
          graded_weeks_set.add(w_num)

    graded_weeks_list = sorted(list(graded_weeks_set))

    st.subheader("🏈 Touchdown Scorer Pick History")
    st.caption("Review your bonus touchdown scorer pick outcomes week by week.")

    all_td_picks = (
        supabase.table("touchdown_picks")
        .select("*")
        .eq("user_id", user_id)
        .order("week_number")
        .execute()
        .data
    )
    if all_td_picks:
      td_history_rows = []
      for td in all_td_picks:
        w_num = td["week_number"]
        p_name = td["player_name"]
        is_c = td.get("is_correct")

        if is_c is None:
          status_str = "⏳ Pending (Awaiting Admin Grading)"
        elif str(is_c).lower() == "true":
          status_str = "✅ Correct (+5 Bonus Tokens)"
        else:
          status_str = "❌ Incorrect (Missed)"

        td_history_rows.append({
            "Week": f"Week {w_num}",
            "Touchdown Scorer Pick": p_name,
            "Result": status_str,
        })
      st.dataframe(
          pd.DataFrame(td_history_rows), use_container_width=True, hide_index=True
      )
    else:
      st.info("No touchdown scorer picks submitted yet.")

    st.divider()
    st.subheader("📋 Detailed Question Bet History")

    history_bets = (
        supabase.table("user_bets")
        .select(
            "*, weekly_questions(week_number, question_number, question_text,"
            " winning_answer)"
        )
        .eq("user_id", user_id)
        .execute()
        .data
    )

    if not history_bets:
      st.info("You haven't placed any question bets yet.")
    else:
      user_history_weeks = sorted(
          list(set([b["week_number"] for b in history_bets]))
      )
      selected_history_week = st.selectbox(
          "Filter History by Week",
          user_history_weeks,
          index=len(user_history_weeks) - 1,
          key="history_week_dropdown_filter",
      )
      st.write("")

      filtered_history_bets = [
          b for b in history_bets if b["week_number"] == selected_history_week
      ]

      if not filtered_history_bets:
        st.info(f"No bets found for Week {selected_history_week}.")
      else:
        formatted_data = []
        for b in filtered_history_bets:
          q_info = b.get("weekly_questions", {})
          w_ans = q_info.get("winning_answer", "Pending")
          raw_q_text = q_info.get("question_text", "N/A")
          clean_q_prompt = (
              raw_q_text.split(" | MATCHUP: ")[0]
              if " | MATCHUP: " in raw_q_text
              else raw_q_text
          )
          q_num = q_info.get("question_number", "?")

          if (
              w_ans in ["Pending", "LOCKED"]
              or w_ans.startswith("LOCKTIME:")
          ):
            outcome = "⏳ Pending"
          elif b["pick"] == w_ans:
            outcome = f"✅ Won (+{b['wager_amount']} 🪙)"
          else:
            outcome = f"❌ Lost (-{b['wager_amount']} 🪙)"

          formatted_data.append({
              "Q#": f"Q{q_num}",
              "Question": clean_q_prompt,
              "Your Pick": b["pick"],
              "Wager": f"{b['wager_amount']} 🪙",
              "Winner": (
                  w_ans
                  if not w_ans.startswith("LOCKTIME:")
                  and w_ans not in ["Pending", "LOCKED"]
                  else "Pending"
              ),
              "Outcome": outcome,
          })

        st.dataframe(
            pd.DataFrame(formatted_data),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Q#": st.column_config.TextColumn("Q#", width="small"),
                "Question": st.column_config.TextColumn(
                    "Question", width="large"
                ),
                "Your Pick": st.column_config.TextColumn(
                    "Your Pick", width="small"
                ),
                "Wager": st.column_config.TextColumn("Wager", width="small"),
                "Winner": st.column_config.TextColumn("Winner", width="small"),
                "Outcome": st.column_config.TextColumn(
                    "Outcome", width="medium"
                ),
            },
        )

    st.divider()

    with st.expander("⚔️ Side-by-Side History Comparison vs. Rival", expanded=False):
      st.caption(
          "Compare your graded week bets side by side against any member in"
          " your leagues in a clean head-to-head match card format!"
      )

      my_league_memberships = (
          supabase.table("league_members")
          .select("league_id")
          .eq("user_id", user_id)
          .execute()
          .data
      )
      my_league_ids = [m["league_id"] for m in my_league_memberships] if my_league_memberships else []

      league_peers_res = (
          supabase.table("league_members")
          .select("user_id, profiles(id, full_name, favorite_team, avatar_emoji)")
          .in_("league_id", my_league_ids)
          .execute()
          .data
      )

      rival_options = {}
      if league_peers_res:
        for lp in league_peers_res:
          p_data = lp.get("profiles")
          if p_data and p_data["id"] != user_id:
            rival_options[p_data["full_name"]] = p_data

      if rival_options and graded_weeks_list:
        col_comp_w, col_comp_r = st.columns(2)
        with col_comp_w:
          comp_week_sel = st.selectbox(
              "Select Graded Week for Comparison",
              graded_weeks_list,
              key="hist_comp_week",
          )
        with col_comp_r:
          comp_rival_name = st.selectbox(
              "Select Rival (League Member)",
              list(rival_options.keys()),
              key="hist_comp_rival",
          )

        rival_prof = rival_options[comp_rival_name]
        rival_id = rival_prof["id"]

        my_hist_bets = (
            supabase.table("user_bets")
            .select(
                "question_id, pick, wager_amount,"
                " weekly_questions(question_number, question_text, winning_answer)"
            )
            .eq("user_id", user_id)
            .eq("week_number", comp_week_sel)
            .order("question_id")
            .execute()
            .data
        )
        rival_hist_bets = (
            supabase.table("user_bets")
            .select("question_id, pick, wager_amount")
            .eq("user_id", rival_id)
            .eq("week_number", comp_week_sel)
            .execute()
            .data
        )
        rival_bets_map = {
            b["question_id"]: (b["pick"], b["wager_amount"])
            for b in rival_hist_bets
        }

        if my_hist_bets:
          st.write("")
          rival_team_info = NFL_TEAM_DATA.get(
              rival_prof.get("favorite_team"),
              NFL_TEAM_DATA["🏈 Free Agent / Neutral"],
          )
          rival_color = rival_team_info["color"]
          rival_avatar = rival_prof.get("avatar_emoji", "🏈")

          st.markdown(
              f"""
                        <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255,255,255,0.12); border-left: 4px solid {rival_color}; padding: 12px 18px; border-radius: 12px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <span style="font-size: 24px;">{rival_avatar}</span>
                                <div>
                                    <b style="color: #fff; font-size: 16px;">Head-to-Head: Week {comp_week_sel} Matchup</b>
                                    <div style="font-size: 12px; color: #94a3b8;">{profile['full_name']} vs. {comp_rival_name}</div>
                                </div>
                            </div>
                            <img src="{rival_team_info['logo']}" style="width: 32px; height: 32px;" />
                        </div>
                    """,
              unsafe_allow_html=True,
          )

          for b in my_hist_bets:
            q_info = b.get("weekly_questions", {})
            q_num = q_info.get("question_number", "?")
            raw_q = q_info.get("question_text", "N/A")
            clean_q = (
                raw_q.split(" | MATCHUP: ")[0]
                if " | MATCHUP: " in raw_q
                else raw_q
            )
            w_ans = q_info.get("winning_answer", "")

            my_pick = b["pick"]
            my_wager = b["wager_amount"]

            riv_data = rival_bets_map.get(b["question_id"], ("Did Not Bet", 0))
            riv_pick = riv_data[0]
            riv_wager = riv_data[1]

            my_won = my_pick == w_ans
            riv_won = riv_pick == w_ans

            my_pill_bg = (
                "rgba(16, 185, 129, 0.18)"
                if my_won
                else "rgba(239, 68, 68, 0.18)"
            )
            my_pill_border = "#10b981" if my_won else "#ef4444"
            my_pill_color = "#34d399" if my_won else "#f87171"
            my_status_text = (
                f"Won (+{my_wager}🪙)" if my_won else f"Lost (-{my_wager}🪙)"
            )

            if riv_pick in ["Yes", "No"]:
              riv_pill_bg = (
                  "rgba(16, 185, 129, 0.18)"
                  if riv_won
                  else "rgba(239, 68, 68, 0.18)"
              )
              riv_pill_border = "#10b981" if riv_won else "#ef4444"
              riv_pill_color = "#34d399" if riv_won else "#f87171"
              riv_status_text = (
                  f"Won (+{riv_wager}🪙)" if riv_won else f"Lost (-{riv_wager}🪙)"
              )
            else:
              riv_pill_bg = "rgba(100, 116, 139, 0.2)"
              riv_pill_border = "#64748b"
              riv_pill_color = "#94a3b8"
              riv_status_text = "Did Not Bet"

            st.markdown(
                f"""
                            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 16px; margin-bottom: 14px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                    <span style="font-family: 'Bebas Neue'; font-size: 20px; color: {user_team_color}; letter-spacing: 1px;">QUESTION {q_num}</span>
                                    <span style="font-size: 13px; color: #cbd5e1; background: rgba(255,255,255,0.08); padding: 2px 10px; border-radius: 8px;">Official Winner: <b style="color: #38bdf8;">{w_ans}</b></span>
                                </div>
                                <div style="font-size: 15px; font-weight: 600; color: #ffffff; margin-bottom: 12px; line-height: 1.4;">{clean_q}</div>
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                                    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px 12px;">
                                        <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">You ({profile['full_name']})</div>
                                        <div style="display: flex; justify-content: space-between; align-items: center;">
                                            <span style="font-size: 15px; font-weight: 700; color: #fff;">Pick: <span style="color: {user_team_color};">{my_pick}</span> ({my_wager}🪙)</span>
                                            <span style="font-size: 12px; font-weight: 600; background: {my_pill_bg}; border: 1px solid {my_pill_border}; color: {my_pill_color}; padding: 2px 8px; border-radius: 6px;">{my_status_text}</span>
                                        </div>
                                    </div>
                                    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 10px 12px;">
                                        <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: bold; margin-bottom: 4px;">{comp_rival_name}</div>
                                        <div style="display: flex; justify-content: space-between; align-items: center;">
                                            <span style="font-size: 15px; font-weight: 700; color: {rival_color};">Pick: {riv_pick} ({riv_wager}🪙)</span>
                                            <span style="font-size: 12px; font-weight: 600; background: {riv_pill_bg}; border: 1px solid {riv_pill_border}; color: {riv_pill_color}; padding: 2px 8px; border-radius: 6px;">{riv_status_text}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        """,
                unsafe_allow_html=True,
            )
        else:
          st.info(
              "You did not place any bets for this selected comparison week."
          )
      else:
        st.info(
            "Side-by-side historical comparison will unlock here automatically"
            " once at least one week has be fully graded by the Admin and you"
            " share a league with other active participants!"
        )

  # ------------------------------------------
  # TAB 5: LEAGUES
  # ------------------------------------------
  with tab_leagues:
    st.header("🏆 League Standings & Mini-Leagues")
    st.caption(
        "Track your standings across the Global Leaderboard and your custom"
        " mini-leagues. Your Nemesis is tracked exclusively within the selected"
        " league!"
    )
    st.write("")

    my_memberships = (
        supabase.table("league_members")
        .select("league_id, leagues(id, league_name, invite_code, created_by)")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    all_my_leagues = [m for m in my_memberships if m.get("leagues")]

    global_league_item = next(
        (
            m
            for m in all_my_leagues
            if m["leagues"]["id"] == "00000000-0000-0000-0000-000000000001"
        ),
        None,
    )
    mini_leagues = [
        m
        for m in all_my_leagues
        if m["leagues"]["id"] != "00000000-0000-0000-0000-000000000001"
    ]

    league_filter_options = {}
    if global_league_item:
      l_obj = global_league_item.get("leagues")
      if l_obj:
        league_filter_options["🏆 Global Leaderboard"] = l_obj["id"]

    for m_item in mini_leagues:
      l_obj = m_item.get("leagues")
      if l_obj:
        league_filter_options[f"🛡️ {l_obj['league_name']} (Mini-League)"] = (
            l_obj["id"]
        )

    if league_filter_options:
      user_saved_default = profile.get(
          "default_league_view", "00000000-0000-0000-0000-000000000001"
      )
      default_label = next(
          (k for k, v in league_filter_options.items() if v == user_saved_default),
          list(league_filter_options.keys())[0],
      )
      default_dropdown_idx = (
          list(league_filter_options.keys()).index(default_label)
          if default_label in league_filter_options
          else 0
      )

      selected_league_filter_label = st.selectbox(
          "Select Standings View",
          list(league_filter_options.keys()),
          index=default_dropdown_idx,
          key="unified_league_view_selector",
      )
      selected_league_filter_id = league_filter_options[
          selected_league_filter_label
      ]

      st.write("")

      is_global_view = (
          selected_league_filter_id == "00000000-0000-0000-0000-000000000001"
      )
      icon_prefix = "🏆" if is_global_view else "🛡️"
      clean_display_name = (
          selected_league_filter_label.replace("🛡️ ", "")
          .replace("🏆 ", "")
          .replace(" (Mini-League)", "")
      )
      st.subheader(f"{icon_prefix} {clean_display_name} Standings")

      if is_global_view:
        allowed_peer_ids = None
      else:
        custom_league_members = (
            supabase.table("league_members")
            .select("user_id")
            .eq("league_id", selected_league_filter_id)
            .execute()
            .data
        )
        allowed_peer_ids = (
            {cm["user_id"] for cm in custom_league_members}
            if custom_league_members
            else set()
        )

      filtered_player_stats = get_cached_leaderboard_stats(
          allowed_peer_ids=allowed_peer_ids
      )

      if not filtered_player_stats:
        st.info("No players found in this standings view yet.")
      else:

        def render_player_row(p, current_rank_val):
          av = p.get("avatar_emoji") or "🏈"
          p_border = p.get("avatar_border") or "solid"
          p_bg_col = p.get("avatar_color") or "#1e3a8a"
          t_info = NFL_TEAM_DATA.get(
              p.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
          )
          win_rate_val = p["win_rate"]
          streak_val = p["streak"]
          p_title = get_earned_title(p["id"])

          showcased = p.get("featured_badges") or []
          if not showcased or not isinstance(showcased, list):
            showcased = p.get("unlocked_badges", [])[:2]
          badges_str = " • ".join(showcased) if showcased else "No Badges"

          podium_class = "leaderboard-row"
          if current_rank_val == 1:
            podium_class, rank_display = podium_class + " podium-rank-1", "🥇 1"
          elif current_rank_val == 2:
            podium_class, rank_display = podium_class + " podium-rank-2", "🥈 2"
          elif current_rank_val == 3:
            podium_class, rank_display = podium_class + " podium-rank-3", "🥉 3"
          else:
            rank_display = f"#{current_rank_val}"

          st.markdown(
              f"""
                        <div class="{podium_class}">
                            <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
                                <span style="font-family: 'Bebas Neue'; font-size: 18px; color: #fbbf24; min-width: 26px;">{rank_display}</span>
                                <div style="border: 2px {p_border} {t_info['color']}; border-radius: 6px; padding: 1px 5px; background: {p_bg_col}; flex-shrink: 0;">
                                    <span style="font-size: 15px;">{av}</span>
                                </div>
                                <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    <b style="font-size: 13px; color: #ffffff;">{p['full_name']}</b> <span style="font-size: 9px; color: #38bdf8;">[{p_title}]</span>
                                    <div class="stat-pill-container">
                                        <span class="stat-pill">🪙 <b>{p['tokens']}</b></span>
                                        <span class="stat-pill">🎯 {win_rate_val}%</span>
                                        <span class="stat-pill">🏈 {p['correct_tds']} TDs</span>
                                        <span class="stat-pill">🔥 {streak_val}</span>
                                        <span class="stat-pill" style="color: #94a3b8; max-width: 130px; overflow: hidden; text-overflow: ellipsis;">🏆 {badges_str}</span>
                                    </div>
                                </div>
                            </div>
                            <div style="text-align: right; flex-shrink: 0; margin-left: 8px;">
                                <span style="font-family: 'Bebas Neue'; font-size: 20px; color: #38bdf8;">{p['tokens']} 🪙</span>
                            </div>
                        </div>
                    """,
              unsafe_allow_html=True,
          )

        if is_global_view:
          current_rank = 1
          prev_score, prev_tds = None, None

          all_ranked_players = []
          for idx, p in enumerate(filtered_player_stats):
            score, tds = p["tokens"], p["correct_tds"]
            if idx > 0 and score == prev_score and tds == prev_tds:
              display_rank = current_rank
            else:
              current_rank, display_rank = idx + 1, idx + 1
            prev_score, prev_tds = score, tds
            all_ranked_players.append((p, display_rank))

          top_10 = all_ranked_players[:10]
          for p_obj, r_num in top_10:
            render_player_row(p_obj, r_num)

          logged_in_entry = next(
              (item for item in all_ranked_players if item[0]["id"] == user_id),
              None,
          )
          if logged_in_entry and logged_in_entry[1] > 10:
            st.markdown(
                "<div style='text-align:center; color:#94a3b8; margin: 8px 0;"
                " font-size: 12px;'>• • • your standing • • •</div>",
                unsafe_allow_html=True,
            )
            render_player_row(logged_in_entry[0], logged_in_entry[1])
        else:
          current_rank = 1
          prev_score, prev_tds = None, None
          for idx, p in enumerate(filtered_player_stats):
            score, tds = p["tokens"], p["correct_tds"]
            if idx > 0 and score == prev_score and tds == prev_tds:
              display_rank = current_rank
            else:
              current_rank, display_rank = idx + 1, idx + 1
            prev_score, prev_tds = score, tds

            render_player_row(p, display_rank)

      st.divider()

      if not is_global_view:
        with st.expander("⚔️ Head-to-Head Player Comparison", expanded=False):
          if filtered_player_stats:
            all_other_names = [
                p["full_name"] for p in filtered_player_stats if p["id"] != user_id
            ]
            if all_other_names:
              compare_name = st.selectbox(
                  "Select Rival to Compare Against:",
                  all_other_names,
                  key="leagues_rival_select",
              )
              my_stat = next(
                  (p for p in filtered_player_stats if p["id"] == user_id),
                  filtered_player_stats[0],
              )
              rival_stat = next(
                  (
                      p
                      for p in filtered_player_stats
                      if p["full_name"] == compare_name
                  ),
                  filtered_player_stats[0],
              )

              c1, c2, c3 = st.columns([3, 1, 3])
              with c1:
                st.markdown(
                    f"""
                                <div class="vs-card">
                                    <h3>{my_stat.get('avatar_emoji', '🏈')} You ({my_stat['full_name']})</h3>
                                    <h2 style="color: {user_team_color};">{my_stat['tokens']} 🪙</h2>
                                    <p><b>Title:</b> {get_earned_title(user_id)}</p>
                                    <p><b>Win Rate:</b> {my_stat['win_rate']}%</p>
                                    <p><b>Correct TDs:</b> {my_stat['correct_tds']}</p>
                                    <p><b>Nemesis:</b> <span style="color:#f87171;">{my_stat['nemesis_name']}</span> ({my_stat['nemesis_score']})</p>
                                </div>
                                """,
                    unsafe_allow_html=True,
                )
              with c2:
                st.markdown(
                    "<h1 style='text-align:center; margin-top:50px;'>VS</h1>",
                    unsafe_allow_html=True,
                )
              with c3:
                r_color = NFL_TEAM_DATA.get(
                    rival_stat.get("favorite_team"),
                    NFL_TEAM_DATA["🏈 Free Agent / Neutral"],
                )["color"]
                r_title = get_earned_title(rival_stat["id"])
                st.markdown(
                    f"""
                                <div class="vs-card">
                                    <h3>{rival_stat.get('avatar_emoji','🏈')} {rival_stat['full_name']}</h3>
                                    <h2 style="color: {r_color};">{rival_stat['tokens']} 🪙</h2>
                                    <p><b>Title:</b> {r_title}</p>
                                    <p><b>Win Rate:</b> {rival_stat['win_rate']}%</p>
                                    <p><b>Correct TDs:</b> {rival_stat['correct_tds']}</p>
                                    <p><b>Nemesis:</b> <span style="color:#f87171;">{rival_stat['nemesis_name']}</span> ({rival_stat['nemesis_score']})</p>
                                </div>
                                """,
                    unsafe_allow_html=True,
                )
          else:
            st.info("No players available for head-to-head comparison.")

        st.divider()

      if not is_global_view:
        with st.expander(
            f"🏛️ {clean_display_name} Hall of Fame Archives", expanded=False
        ):
          try:
            archives_res = (
                supabase.table("archived_seasons")
                .select("season_label, standings_json, archived_at")
                .eq("league_id", selected_league_filter_id)
                .order("archived_at", desc=True)
                .execute()
                .data
            )
          except Exception:
            archives_res = []

          if not archives_res:
            st.info(
                "No past season archives found yet for this mini-league."
                " Archived seasons will appear here once the commissioner"
                " concludes and archives a season!"
            )
          else:
            archive_labels = [a["season_label"] for a in archives_res]
            selected_archive_label = st.selectbox(
                "Select Season Archive",
                archive_labels,
                key=f"hof_archive_sel_{selected_league_filter_id}",
            )

            selected_archive_data = next(
                (a for a in archives_res if a["season_label"] == selected_archive_label),
                None,
            )

            if selected_archive_data and selected_archive_data.get(
                "standings_json"
            ):
              standings_list = selected_archive_data["standings_json"]
              champ_entry = (
                  standings_list[0]
                  if standings_list
                  else {"full_name": "TBD", "tokens": 0}
              )

              st.markdown(
                  f"""
                                <div class="champion-card">
                                    <div style="font-size: 20px; letter-spacing: 2px;">👑 {selected_archive_label.upper()} CHAMPION ({clean_display_name})</div>
                                    <div style="font-size: 48px; font-weight: 900; margin: 8px 0;">{champ_entry.get('full_name')} ({champ_entry.get('tokens')} 🪙)</div>
                                    <div style="font-size: 16px;">Crowned the ultimate victor of {clean_display_name}!</div>
                                </div>
                            """,
                  unsafe_allow_html=True,
              )

              formatted_archive_rows = []
              for idx, row in enumerate(standings_list):
                r_icon = (
                    "🥇"
                    if idx == 0
                    else (
                        "🥈"
                        if idx == 1
                        else ("🥉" if idx == 2 else f"#{idx+1}")
                    )
                )
                formatted_archive_rows.append({
                    "Rank": r_icon,
                    "Player": row.get(
                        "full_name", row.get("Player", "Unknown")
                    ),
                    "Final Tokens": row.get(
                        "tokens", row.get("Final Tokens", 0)
                    ),
                    "Favorite Team": row.get("favorite_team", "N/A"),
                })

              st.subheader(
                  f"📜 {selected_archive_label} Official Season Final Standings"
                  f" — {clean_display_name}"
              )
              st.dataframe(
                  pd.DataFrame(formatted_archive_rows),
                  use_container_width=True,
                  hide_index=True,
              )

        st.divider()

      if not is_global_view:
        chat_target_id = selected_league_filter_id
        st.subheader(f"💬 {clean_display_name} Trash Talk Feed")

        with st.form(f"trash_talk_form_{selected_league_filter_id}"):
          chat_msg = st.text_input(
              "Post a message to this mini-league...",
              key=f"chat_input_{selected_league_filter_id}",
          )
          post_chat = st.form_submit_button("Post Message 💬")

          if post_chat and chat_msg.strip():
            if contains_profanity(chat_msg):
              st.error(
                  "⚠️ Your message contains restricted language. Please keep chat"
                  " friendly!"
              )
            else:
              try:
                supabase.table("trash_talk").insert({
                    "user_id": user_id,
                    "message": chat_msg.strip(),
                    "league_id": chat_target_id,
                }).execute()
                st.success("Message posted!")
                st.rerun()
              except Exception as e:
                st.error(f"Error posting message: {e}")

        recent_chats = (
            supabase.table("trash_talk")
            .select("message, created_at, user_id")
            .eq("league_id", chat_target_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
            .data
        )
        all_profiles_chat = get_cached_profiles()
        profile_map_chat = {p["id"]: p for p in all_profiles_chat}

        if recent_chats:
          for c in recent_chats:
            p_info = profile_map_chat.get(c["user_id"], {})
            author_name = p_info.get("full_name", "Player")
            author_av = p_info.get("avatar_emoji", "🏈")
            author_team = p_info.get("favorite_team", "🏈 Free Agent / Neutral")
            t_info = NFL_TEAM_DATA.get(
                author_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"]
            )

            st.markdown(
                f"""
                        <div class="chat-bubble" style="border-left: 5px solid {t_info['color']} !important;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <img src="{t_info['logo']}" style="width:24px; height:24px;" />
                                <b>{author_av} {author_name}</b> <small style="opacity:0.7;">({author_team})</small>
                            </div>
                            <div style="margin-top:4px;">{c['message']}</div>
                        </div>
                        """,
                unsafe_allow_html=True,
            )
        else:
          st.info(
              "No messages in this mini-league feed yet. Be the first to start"
              " the trash talk!"
          )

    st.divider()

    st.subheader("⚙️ Default Standings View")
    st.caption(
        "Configure which league standings view automatically displays when you"
        " open the Leagues tab."
    )

    with st.form("settings_league_tab_form"):
      curr_def_l = profile.get(
          "default_league_view", "00000000-0000-0000-0000-000000000001"
      )
      league_s_options = {}
      for m_item in all_my_leagues:
        l_obj = m_item.get("leagues")
        if l_obj:
          if l_obj["id"] == "00000000-0000-0000-0000-000000000001":
            league_s_options["🏆 Global Leaderboard"] = l_obj["id"]
          else:
            league_s_options[f"🛡️ {l_obj['league_name']} (Mini-League)"] = (
                l_obj["id"]
            )

      default_keys_list = list(league_s_options.keys())
      def_s_label = next(
          (k for k, v in league_s_options.items() if v == curr_def_l),
          default_keys_list[0] if default_keys_list else "🏆 Global Leaderboard",
      )
      s_index = (
          default_keys_list.index(def_s_label)
          if def_s_label in default_keys_list
          else 0
      )

      new_def_league_label = st.selectbox(
          "Default Standings View",
          default_keys_list,
          index=s_index,
          key="leagues_tab_default_view_select",
      )
      new_def_league_id = league_s_options[new_def_league_label]

      save_def_league = st.form_submit_button("Save Default View 💾", type="primary")
      if save_def_league:
        supabase.table("profiles").update(
            {"default_league_view": new_def_league_id}
        ).eq("id", user_id).execute()
        st.success("Default standings view updated successfully!")
        st.rerun()

    st.divider()

    st.subheader("➕ Create or Join Custom Leagues")

    col_create, col_join = st.columns(2)

    with col_create:
      st.markdown("#### Create a League")
      with st.form("create_league_form"):
        new_league_name = st.text_input(
            "League Name", placeholder="e.g., Office Chumps"
        )
        new_league_pwd = st.text_input(
            "League Password / Passcode (Optional)",
            type="password",
            placeholder="Secure access code",
        )
        submit_create_league = st.form_submit_button(
            "Create League 🚀", type="primary"
        )

        if submit_create_league:
          if not new_league_name.strip():
            st.error("Please enter a valid league name.")
          elif contains_profanity(new_league_name):
            st.error(
                "⚠️ League name contains restricted language. Please choose"
                " appropriate wording."
            )
          else:
            import random as r_mod
            import string as s_mod

            invite_code = "".join(
                r_mod.choices(s_mod.ascii_uppercase + s_mod.digits, k=6)
            )
            try:
              res_l = (
                  supabase.table("leagues")
                  .insert({
                      "league_name": new_league_name.strip(),
                      "invite_code": invite_code,
                      "created_by": user_id,
                      "league_password": (
                          new_league_pwd.strip() if new_league_pwd else ""
                      ),
                  })
                  .execute()
              )

              if res_l.data:
                new_league_id = res_l.data[0]["id"]
                supabase.table("league_members").insert({
                    "league_id": new_league_id,
                    "user_id": user_id,
                }).execute()
                st.success(
                    f"League '{new_league_name}' created successfully! Invite"
                    f" Code: **{invite_code}**"
                )
                st.rerun()
            except Exception as e:
              st.error(f"Error creating league: {e}")

    with col_join:
      st.markdown("#### Join a League")
      with st.form("join_league_form"):
        code_input = st.text_input(
            "Enter 6-Character Invite Code", placeholder="e.g., A7X9P2"
        )
        pwd_input = st.text_input(
            "League Password (if required)",
            type="password",
            placeholder="Enter password",
        )
        submit_join_league = st.form_submit_button("Join League 🤝", type="primary")

        if submit_join_league:
          clean_code = code_input.strip().upper()
          if not clean_code:
            st.warning("Please enter an invite code.")
          else:
            found_league = (
                supabase.table("leagues")
                .select("id, league_name, league_password")
                .eq("invite_code", clean_code)
                .execute()
                .data
            )
            if not found_league:
              st.error(
                  "Invalid invite code. Please check with your league"
                  " commissioner."
              )
            else:
              target_league = found_league[0]
              target_league_id = target_league["id"]
              stored_pwd = target_league.get("league_password", "")

              if stored_pwd and stored_pwd != pwd_input.strip():
                st.error(
                    "Incorrect league password. Please check with the"
                    " commissioner."
                )
              else:
                existing_member = (
                    supabase.table("league_members")
                    .select("id")
                    .eq("league_id", target_league_id)
                    .eq("user_id", user_id)
                    .execute()
                    .data
                )
                if existing_member:
                  st.warning(
                      f"You are already a member of"
                      f" '{target_league['league_name']}'!"
                  )
                else:
                  supabase.table("league_members").insert({
                      "league_id": target_league_id,
                      "user_id": user_id,
                  }).execute()
                  st.success(
                      f"Successfully joined '{target_league['league_name']}'!"
                  )
                  st.rerun()

    st.write("")
    st.markdown("#### 📋 Your Joined Mini-Leagues")

    if mini_leagues:
      for mem in mini_leagues:
        league_info = mem.get("leagues")
        if league_info:
          l_name = league_info["league_name"]
          l_code = league_info["invite_code"]
          l_creator = league_info["created_by"]
          is_commissioner_here = (l_creator == user_id) or profile.get(
              "is_admin", False
          )

          members_res = (
              supabase.table("league_members")
              .select("user_id")
              .eq("league_id", league_info["id"])
              .execute()
              .data
          )
          member_count = len(members_res) if members_res else 0

          st.markdown(
              f"""
                        <div class="summary-box">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h3 style="margin: 0; color: #ffffff;">🛡️ {l_name} { '⭐ (You are Commissioner)' if is_commissioner_here else '' }</h3>
                                    <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Invite Code: <b style="color: #38bdf8; letter-spacing: 1px;">{l_code}</b> | Members: <b>{member_count}</b></p>
                                </div>
                            </div>
                        </div>
                    """,
              unsafe_allow_html=True,
          )

  # ------------------------------------------
  # TAB 6: SETTINGS
  # ------------------------------------------
  with tab_settings:
    st.header("⚙️ Account & App Settings")
    st.caption(
        "Manage your account security, notification preferences, and"
        " accessibility options."
    )
    st.write("")

    st.subheader("🔐 Account Security")

    with st.form("settings_password_form"):
      st.markdown("##### Request Password Reset Email")
      st.caption("Send a secure password reset link directly to your registered email address.")
      
      submit_pass_reset_email = st.form_submit_button("Send Password Reset Email 🔑", type="primary")
      if submit_pass_reset_email:
        try:
          user_email_addr = st.session_state.user.email
          admin_supabase = supabase
          service_key = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", "")
          url = os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
          
          if service_key and url:
            admin_supabase = create_client(url, service_key)

          response = admin_supabase.auth.admin.generate_link(
              {"type": "recovery", "email": user_email_addr}
          )

          if response and hasattr(response, "properties") and response.properties:
            recovery_link = getattr(response.properties, "action_link", None)
            
            if not recovery_link and isinstance(response.properties, dict):
              recovery_link = response.properties.get("action_link")

            if recovery_link:
              html_content = f"""
                      <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
                          <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                              
                              <div style="text-align: center; margin-bottom: 30px;">
                                  <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Touchdown Tokens Logo" style="width: 180px; margin-bottom: 15px; filter: drop-shadow(0px 6px 15px rgba(251, 191, 36, 0.4));" />
                                  <h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                                  <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Password Reset Request</p>
                              </div>

                              <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Reset Your Password 🔑</h3>
                              <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                                  We received a request to reset your Touchdown Tokens password from your account settings. Click the button below to choose a new password:
                              </p>

                              <div style="text-align: center; margin: 35px 0;">
                                  <a href="{recovery_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; letter-spacing: 1px; display: inline-block; box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);">RESET PASSWORD</a>
                              </div>

                              <p style="color: #94a3b8; font-size: 13px; line-height: 1.5; margin-top: 30px; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 20px;">
                                  If you did not request a password reset, you can safely ignore this email.
                              </p>
                          </div>
                      </div>
                      """

              params = {
                  "from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>",
                  "to": [user_email_addr],
                  "subject": "🔑 Reset Your Touchdown Tokens Password",
                  "html": html_content,
              }
              resend.Emails.send(params)
              st.success("Password reset email sent to your inbox!")
            else:
              st.error("Could not retrieve recovery link properties from the response.")
          else:
            st.error("Could not generate recovery link for this email.")
        except Exception as e:
          st.error(f"Error sending password reset email: {e}")

    with st.form("settings_email_form"):
      st.markdown("##### Change Registered Email")
      st.caption(f"Current Email: `{st.session_state.user.email}`")
      new_email_input = st.text_input(
          "New Email Address", key="settings_new_email"
      )

      submit_email = st.form_submit_button("Update Email ✉️")
      if submit_email:
        if not new_email_input.strip() or "@" not in new_email_input:
          st.warning("Please enter a valid email address.")
        else:
          try:
            supabase.auth.update_user({"email": new_email_input.strip()})
            supabase.table("profiles").update(
                {"email": new_email_input.strip()}
            ).eq("id", user_id).execute()
            st.success(
                "Email update requested! Check your new email inbox for"
                " confirmation."
            )
          except Exception as e:
            st.error(f"Error updating email: {e}")

    st.divider()

    st.subheader("🔔 Notification Preferences")
    with st.form("settings_notifications_form"):
      curr_notif = profile.get("email_notifications", True)
      new_notif = st.toggle(
          "Enable Email / In-App Result Alerts & Reminders", value=curr_notif
      )

      save_notif = st.form_submit_button("Save Notification Settings 💾")
      if save_notif:
        supabase.table("profiles").update(
            {"email_notifications": new_notif}
        ).eq("id", user_id).execute()
        st.success("Notification preferences saved!")
        st.rerun()

    st.divider()

    st.subheader("♿ Accessibility & Display Preferences")
    with st.form("settings_accessibility_form"):
      curr_hc = profile.get("high_contrast_mode", False)
      curr_rm = profile.get("reduced_motion", False)

      new_hc = st.toggle(
          "High Contrast Mode (Enhanced text legibility)", value=curr_hc
      )
      new_rm = st.toggle(
          "Reduced Motion (Disable glowing animations & pulses)", value=curr_rm
      )

      save_access = st.form_submit_button("Save Accessibility Settings 💾")
      if save_access:
        supabase.table("profiles").update({
            "high_contrast_mode": new_hc,
            "reduced_motion": new_rm,
        }).eq("id", user_id).execute()
        st.success("Accessibility preferences saved!")
        st.rerun()

  # ------------------------------------------
  # TAB: LEAGUE ADMIN
  # ------------------------------------------
  if is_any_league_admin:
    with tab_league_admin:
      st.markdown("## ⭐ League Commissioner Administration")
      st.caption(
          "Manage your mini-leagues, update settings, adjust member token"
          " balances, regenerate invite codes, and handle member rosters."
      )
      st.write("")

      admin_leagues_list = []
      if profile.get("is_admin"):
        all_custom_leagues = (
            supabase.table("leagues")
            .select("id, league_name, invite_code, league_password, created_by")
            .neq("id", "00000000-0000-0000-0000-000000000001")
            .execute()
            .data
        )
        admin_leagues_list = all_custom_leagues if all_custom_leagues else []
      else:
        admin_leagues_list = my_administered_leagues

      if not admin_leagues_list:
        st.info(
            "You are not currently designated as a commissioner for any custom"
            " mini-leagues."
        )
      else:
        league_options_map = {l["league_name"]: l for l in admin_leagues_list}
        selected_admin_league_name = st.selectbox(
            "Select Mini-League to Administer",
            list(league_options_map.keys()),
            key="league_admin_selector",
        )
        selected_league = league_options_map[selected_admin_league_name]
        l_id = selected_league["id"]
        l_name = selected_league["league_name"]
        l_code = selected_league["invite_code"]

        st.write("")

        members_res = (
            supabase.table("league_members")
            .select("user_id, profiles(full_name, tokens, favorite_team)")
            .eq("league_id", l_id)
            .execute()
            .data
        )
        member_count = len(members_res) if members_res else 0

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
          st.metric("League Name", l_name)
        with col_m2:
          st.metric("Invite Code", l_code)
        with col_m3:
          st.metric("Total Members", str(member_count))

        st.write("")

        with st.expander("📝 1. League Settings & Security", expanded=True):
          with st.form(f"redesigned_league_settings_{l_id}"):
            new_l_name = st.text_input("League Name", value=l_name)
            new_l_pwd = st.text_input(
                "League Password / Passcode (Leave blank for public)",
                type="password",
                placeholder="Secure access code",
            )

            save_settings_btn = st.form_submit_button(
                "Save League Settings 💾", type="primary"
            )
            if save_settings_btn:
              if not new_l_name.strip():
                st.error("League name cannot be blank.")
              elif contains_profanity(new_l_name):
                st.error(
                    "⚠️ League name contains restricted language. Please choose"
                    " appropriate wording."
                )
              else:
                supabase.table("leagues").update({
                    "league_name": new_l_name.strip(),
                    "league_password": new_l_pwd.strip() if new_l_pwd else "",
                }).eq("id", l_id).execute()
                st.success("League settings updated successfully!")
                st.rerun()

        with st.expander(
            "🪙 2. Member Token Balances & Adjustments", expanded=False
        ):
          st.caption(
              "Add, subtract, or set exact token balances for members in this"
              " league."
          )
          if members_res:
            with st.form(f"redesigned_token_adj_{l_id}"):
              all_m_map = {
                  m.get("profiles", {}).get("full_name", "Unknown"): m["user_id"]
                  for m in members_res
                  if m.get("profiles")
              }
              target_member_name = st.selectbox(
                  "Select Member", list(all_m_map.keys())
              )
              token_adj_mode = st.selectbox(
                  "Operation",
                  ["Add Tokens", "Subtract Tokens", "Set Exact Balance"],
              )
              token_adj_val = st.number_input(
                  "Token Amount", min_value=0, value=5, step=1
              )

              submit_comm_adjust = st.form_submit_button(
                  "Apply Token Adjustment 🪙", type="primary"
              )
              if submit_comm_adjust:
                t_uid = all_m_map[target_member_name]
                curr_user_prof = (
                    supabase.table("profiles")
                    .select("tokens")
                    .eq("id", t_uid)
                    .single()
                    .execute()
                    .data
                )
                curr_toks = (
                    curr_user_prof.get("tokens", 10) if curr_user_prof else 10
                )

                if token_adj_mode == "Add Tokens":
                  new_toks = curr_toks + token_adj_val
                elif token_adj_mode == "Subtract Tokens":
                  new_toks = max(0, curr_toks - token_adj_val)
                else:
                  new_toks = token_adj_val

                supabase.table("profiles").update({"tokens": new_toks}).eq(
                    "id", t_uid
                ).execute()
                st.success(
                    f"Successfully updated {target_member_name}'s balance to"
                    f" {new_toks} tokens!"
                )
                st.rerun()
          else:
            st.info("No members in this league.")

        with st.expander("👥 3. Roster & Member Removal", expanded=False):
          st.caption("Remove players from your league roster if necessary.")
          if members_res:
            member_names_map = {
                m.get("profiles", {}).get("full_name", "Unknown Player"): m[
                    "user_id"
                ]
                for m in members_res
                if m.get("profiles") and m["user_id"] != user_id
            }

            if member_names_map:
              with st.form(f"redesigned_kick_form_{l_id}"):
                target_kick_name = st.selectbox(
                    "Select Member to Kick / Remove",
                    list(member_names_map.keys()),
                )
                confirm_kick = st.checkbox(
                    f"I confirm I want to remove {target_kick_name} from"
                    f" {l_name}"
                )

                submit_kick = st.form_submit_button(
                    "Remove Member from League 🚪", type="secondary"
                )
                if submit_kick:
                  if not confirm_kick:
                    st.warning(
                        f"Please check the confirmation box to remove"
                        f" {target_kick_name}."
                    )
                  else:
                    t_kick_uid = member_names_map[target_kick_name]
                    supabase.table("league_members").delete().eq(
                        "league_id", l_id
                    ).eq("user_id", t_kick_uid).execute()
                    st.success(
                        f"Successfully removed {target_kick_name} from {l_name}."
                    )
                    st.rerun()
            else:
              st.info("No other members in this league to remove.")

        with st.expander("👑 4. Conclude Season & Crown Champion", expanded=False):
          st.caption(
              "Snapshot current mini-league standings, crown the #1 player as"
              " Champion, and archive the season into your Hall of Fame."
          )

          with st.form(f"conclude_season_form_{l_id}"):
            season_label_input = st.text_input(
                "Season Label / Title",
                value="2026 Season",
                placeholder="e.g., 2026 Office Chumps Season",
            )
            confirm_conclude = st.checkbox(
                f"I confirm I want to conclude the season for {l_name}, archive"
                " standings, and crown the winner."
            )

            submit_conclude = st.form_submit_button(
                "Crown Champion & Archive Season 🏆", type="primary"
            )
            if submit_conclude:
              if not confirm_conclude:
                st.warning("Please check the confirmation box to proceed.")
              else:
                try:
                  all_profiles_snapshot = get_cached_profiles()
                  league_member_ids = (
                      {m["user_id"] for m in members_res}
                      if members_res
                      else set()
                  )

                  league_players = [
                      p
                      for p in all_profiles_snapshot
                      if p["id"] in league_member_ids
                  ]
                  league_players_sorted = sorted(
                      league_players, key=lambda x: (-x["tokens"], x["full_name"])
                  )

                  if league_players_sorted:
                    champ_user_id = league_players_sorted[0]["id"]
                    champ_prof = (
                        supabase.table("profiles")
                        .select("unlocked_badges")
                        .eq("id", champ_user_id)
                        .single()
                        .execute()
                        .data
                    )
                    if champ_prof:
                      unlocked_b = champ_prof.get("unlocked_badges", [])
                      if not isinstance(unlocked_b, list):
                        unlocked_b = []
                      if "🏆 League Champion" not in unlocked_b:
                        unlocked_b.append("🏆 League Champion")
                        supabase.table("profiles").update({
                            "unlocked_badges": unlocked_b,
                            "selected_title": "👑 League Champion",
                        }).eq("id", champ_user_id).execute()

                  supabase.table("archived_seasons").insert({
                      "league_id": l_id,
                      "season_label": season_label_input.strip(),
                      "standings_json": league_players_sorted,
                  }).execute()

                  st.cache_data.clear()
                  st.balloons()
                  st.success(
                      f"Successfully concluded '{season_label_input}' for"
                      f" {l_name}! Champion crowned and archived to Hall of"
                      " Fame."
                  )
                  st.rerun()
                except Exception as e:
                  st.error(f"Error concluding season: {e}")

        with st.expander("🔑 5. Invite Code & Ownership Tools", expanded=False):
          col_tc1, col_tc2 = st.columns(2)
          with col_tc1:
            st.markdown("##### Regenerate Invite Code")
            st.caption(
                "Generate a brand new 6-character code, invalidating the old"
                " one."
            )
            if st.button("Generate New Invite Code 🔑", key=f"btn_regen_{l_id}"):
              import random as r_m
              import string as s_m

              new_code = "".join(
                  r_m.choices(s_m.ascii_uppercase + s_m.digits, k=6)
              )
              supabase.table("leagues").update({"invite_code": new_code}).eq(
                  "id", l_id
              ).execute()
              st.success(f"New invite code generated: **{new_code}**")
              st.rerun()

          with col_tc2:
            st.markdown("##### Transfer Ownership")
            st.caption("Transfer commissioner rights to another member.")
            other_member_names = {
                m.get("profiles", {}).get("full_name", "Unknown"): m["user_id"]
                for m in members_res
                if m.get("profiles") and m["user_id"] != user_id
            }
            if other_member_names:
              with st.form(f"redesigned_transfer_{l_id}"):
                new_owner_name = st.selectbox(
                    "Select New Commissioner", list(other_member_names.keys())
                )
                submit_transfer = st.form_submit_button("Transfer Ownership 👑")
                if submit_transfer:
                  new_owner_id = other_member_names[new_owner_name]
                  supabase.table("leagues").update(
                      {"created_by": new_owner_id}
                  ).eq("id", l_id).execute()
                  st.success(
                      f"Successfully transferred commissioner ownership to"
                      f" {new_owner_name}!"
                  )
                  st.rerun()
            else:
              st.info("No other members available for transfer.")

  # ------------------------------------------
  # TAB: SYSTEM ADMIN CONTROL
  # ------------------------------------------
  if profile.get("is_admin"):
    with tab_admin:
      st.header("⚙️ System Admin Management Portal")

      admin_sec = st.radio(
          "Select Action",
          [
              "Manage Questions",
              "Auto-Lockout Scheduler",
              "Grade Week & Calculate Points",
              "Bulk Token Adjuster",
              "Export League Data (CSV)",
              "League Chat Announcement",
              "Archive & Reset Season",
              "App Access Control",
          ],
          horizontal=True,
      )

      if admin_sec == "Manage Questions":
        st.subheader("📋 Manage & Edit Weekly Questions & Matchups")
        st.caption(
            "Select a week below to view, publish, or edit questions and"
            " matchups dynamically. They will stay right here for ongoing"
            " edits!"
        )

        all_db_weeks = (
            supabase.table("weekly_questions")
            .select("week_number")
            .neq("week_number", 999)
            .neq("week_number", 998)
            .neq("week_number", 997)
            .neq("week_number", 96)
            .execute()
            .data
        )
        db_week_nums = (
            sorted(list(set([r["week_number"] for r in all_db_weeks])))
            if all_db_weeks
            else []
        )
        next_suggested_week = (db_week_nums[-1] + 1) if db_week_nums else 1

        week_options = (
            db_week_nums + [next_suggested_week]
            if next_suggested_week not in db_week_nums
            else db_week_nums
        )
        selected_manage_week = st.selectbox(
            "Select Week to Manage",
            week_options,
            index=len(week_options) - 1,
            key="admin_manage_week_sel",
        )

        existing_week_qs = get_cached_weekly_questions(selected_manage_week)
        real_existing_qs = {
            q["question_number"]: q
            for q in existing_week_qs
            if q.get("question_number", 0) <= 10
        }

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
          if st.button("📋 Load 10 Default Question Templates"):
            for i in range(1, 11):
              st.session_state[f"m_prompt_w{selected_manage_week}_q{i}"] = (
                  DEFAULT_QUESTION_TEMPLATES[i - 1]
              )
            st.success("Default templates loaded instantly!")
            st.rerun()
        with col_btn2:
          if st.button(
              "🗑️ Clear Unpublished Questions",
              help="Deletes all unpublished questions for this week",
          ):
            try:
              supabase.table("weekly_questions").delete().eq(
                  "week_number", selected_manage_week
              ).eq("winning_answer", "Pending").execute()
              for i in range(1, 11):
                skey = f"m_prompt_w{selected_manage_week}_q{i}"
                if skey in st.session_state:
                  del st.session_state[skey]
              st.cache_data.clear()
              st.success(
                  f"Cleared unpublished questions for Week {selected_manage_week}!"
              )
              st.rerun()
            except Exception as e:
              st.error(f"Error clearing questions: {e}")

        with st.form(key=f"manage_questions_form_week_{selected_manage_week}"):
          question_payloads = []

          for i in range(1, 11):
            st.markdown(f"#### Question {i}")

            q_obj = real_existing_qs.get(i, {})
            raw_txt = q_obj.get("question_text", "")

            db_prompt = (
                raw_txt.split(" | MATCHUP: ")[0]
                if " | MATCHUP: " in raw_txt
                else raw_txt
            )
            session_key = f"m_prompt_w{selected_manage_week}_q{i}"
            existing_prompt = st.session_state.get(session_key, db_prompt)

            existing_away = "🏈 Free Agent / Neutral"
            existing_home = "🏈 Free Agent / Neutral"

            if " | MATCHUP: " in raw_txt:
              matchup_part = raw_txt.split(" | MATCHUP: ")[1]
              if " @ " in matchup_part:
                split_teams = matchup_part.split(" @ ")
                existing_away = (
                    split_teams[0]
                    if split_teams[0] in NFL_TEAMS
                    else "🏈 Free Agent / Neutral"
                )
                existing_home = (
                    split_teams[1]
                    if split_teams[1] in NFL_TEAMS
                    else "🏈 Free Agent / Neutral"
                )

            col_m1, col_m2 = st.columns(2)
            with col_m1:
              away_t = st.selectbox(
                  f"Q{i} Away Team",
                  NFL_TEAMS,
                  index=(
                      NFL_TEAMS.index(existing_away)
                      if existing_away in NFL_TEAMS
                      else 0
                  ),
                  key=f"m_away_w{selected_manage_week}_q{i}",
              )
            with col_m2:
              home_t = st.selectbox(
                  f"Q{i} Home Team",
                  NFL_TEAMS,
                  index=(
                      NFL_TEAMS.index(existing_home)
                      if existing_home in NFL_TEAMS
                      else 0
                  ),
                  key=f"m_home_w{selected_manage_week}_q{i}",
              )

            prompt_val = st.text_input(
                f"Question {i} Prompt", value=existing_prompt, key=session_key
            )

            question_payloads.append({
                "question_number": i,
                "prompt": prompt_val.strip(),
                "away": away_t,
                "home": home_t,
                "db_id": q_obj.get("id"),
            })
            st.divider()

          save_all_questions_btn = st.form_submit_button(
              "Save & Publish All Questions 💾", type="primary"
          )

          if save_all_questions_btn:
            has_profane_q = any(
                contains_profanity(item["prompt"]) for item in question_payloads
            )
            if has_profane_q:
              st.error(
                  "⚠️ One or more question prompts contain restricted language."
                  " Please edit them before publishing."
              )
            else:
              for item in question_payloads:
                if item["prompt"]:
                  combined_text = (
                      f"{item['prompt']} | MATCHUP: {item['away']} @"
                      f" {item['home']}"
                  )

                  if item["db_id"]:
                    supabase.table("weekly_questions").update(
                        {"question_text": combined_text}
                    ).eq("id", item["db_id"]).execute()
                  else:
                    supabase.table("weekly_questions").insert({
                        "week_number": selected_manage_week,
                        "question_number": item["question_number"],
                        "question_text": combined_text,
                        "winning_answer": "Pending",
                    }).execute()

              st.cache_data.clear()
              st.balloons()
              st.success(
                  f"Successfully saved and updated Week {selected_manage_week}"
                  " questions!"
              )
              st.rerun()

      elif admin_sec == "Auto-Lockout Scheduler":
        st.subheader("⏰ Auto-Lockout Scheduler & Emergency Override")
        lock_week = st.number_input(
            "Select Week", min_value=1, max_value=24, step=1, key="admin_lock_week"
        )

        existing_lock_row = (
            supabase.table("weekly_questions")
            .select("winning_answer")
            .eq("week_number", lock_week)
            .eq("question_number", 99)
            .execute()
            .data
        )
        current_lock_val = (
            existing_lock_row[0]["winning_answer"]
            if existing_lock_row
            else "Not Set"
        )

        st.info(f"Current Lock Status for Week {lock_week}: `{current_lock_val}`")

        col_sch1, col_sch2 = st.columns(2)
        with col_sch1:
          lock_date = st.date_input("Automatic Lockout Date (UTC)")
          lock_time = st.time_input("Automatic Lockout Time (UTC)")
        with col_sch2:
          st.write("")
          st.write("")
          manual_override_toggle = st.toggle(
              "🚨 Manual Emergency Lockout Override",
              value=(current_lock_val == "LOCKED"),
          )

        if st.button("Save Lockout Configuration 🔒", type="primary"):
          if manual_override_toggle:
            supabase.table("weekly_questions").delete().eq(
                "week_number", lock_week
            ).eq("question_number", 99).execute()
            supabase.table("weekly_questions").insert({
                "week_number": lock_week,
                "question_number": 99,
                "question_text": "WEEK LOCKOUT TIMESTAMP",
                "winning_answer": "LOCKED",
            }).execute()
            st.cache_data.clear()
            st.success(
                f"Week {lock_week} has been MANUALLY LOCKED by Admin override!"
            )
          else:
            combined_dt = datetime.combine(lock_date, lock_time).isoformat()
            supabase.table("weekly_questions").delete().eq(
                "week_number", lock_week
            ).eq("question_number", 99).execute()
            supabase.table("weekly_questions").insert({
                "week_number": lock_week,
                "question_number": 99,
                "question_text": "WEEK LOCKOUT TIMESTAMP",
                "winning_answer": f"LOCKTIME:{combined_dt}",
            }).execute()
            st.cache_data.clear()
            st.success(
                f"Auto-lockout scheduled for Week {lock_week} at {combined_dt}"
                " UTC!"
            )

      elif admin_sec == "Grade Week & Calculate Points":
        st.subheader("Grade Weekly Results & Live Score Feeder")
        grade_week = st.number_input(
            "Select Week to Grade", min_value=1, max_value=24, step=1, key="grade_week_num"
        )

        status_row = (
            supabase.table("weekly_questions")
            .select("winning_answer")
            .eq("week_number", grade_week)
            .eq("question_number", 96)
            .execute()
            .data
        )
        is_week_closed = (
            status_row and status_row[0]["winning_answer"] == "CLOSED"
        )

        if is_week_closed:
          st.warning(
              f"🔒 **Week {grade_week} is currently CLOSED and has already been"
              " graded.**"
          )
          col_reopen1, col_reopen2 = st.columns([2, 2])
          with col_reopen1:
            if st.button(
                f"🔓 Reopen Week {grade_week} for Regrading", type="secondary"
            ):
              supabase.table("weekly_questions").delete().eq(
                  "week_number", grade_week
              ).eq("question_number", 96).execute()

              all_users_reopen = (
                  supabase.table("profiles").select("id").execute().data
              )
              for u in all_users_reopen:
                supabase.table("profiles").update({"tokens": 10}).eq(
                    "id", u["id"]
                ).execute()
              recalculate_all_user_balances(supabase)

              st.cache_data.clear()
              st.success(
                  f"Week {grade_week} has been reopened and balances restored"
                  " successfully!"
              )
              st.rerun()
          st.divider()

        with st.expander("⚡ Fetch Live ESPN Scores for Reference", expanded=False):
          st.caption(
              "Pull live game scores from ESPN to verify outcomes before"
              " grading below."
          )
          if st.button("🔄 Fetch Live Scores Now"):
            try:
              espn_url = (
                  "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
              )
              resp = requests.get(espn_url, timeout=10)
              if resp.status_code == 200:
                data = resp.json()
                events = data.get("events", [])
                st.success(f"Connected to ESPN! Found {len(events)} games.")

                game_results_cache = {}
                for ev in events:
                  comp = ev.get("competitions", [{}])[0]
                  status_type = (
                      ev.get("status", {}).get("type", {}).get("name", "")
                  )
                  competitors = comp.get("competitors", [])

                  home_team_abbr = ""
                  away_team_abbr = ""
                  home_score = 0
                  away_score = 0

                  for team_obj in competitors:
                    abbr = (
                        team_obj.get("team", {}).get("abbreviation", "")
                    )
                    score = int(team_obj.get("score", 0))
                    if team_obj.get("homeAway") == "home":
                      home_team_abbr = abbr
                      home_score = score
                    else:
                      away_team_abbr = abbr
                      away_score = score

                  if status_type == "STATUS_FINAL":
                    game_results_cache[f"{away_team_abbr} @ {home_team_abbr}"] = {
                        "status": "FINAL",
                        "home_score": home_score,
                        "away_score": away_score,
                    }
                st.session_state["espn_fetched_scores"] = game_results_cache
              else:
                st.error("Failed to reach ESPN scoreboard API.")
            except Exception as e:
              st.error(f"API Error: {e}")

          if "espn_fetched_scores" in st.session_state:
            st.write("**Live API Game Status Feed:**")
            fetched_map = st.session_state["espn_fetched_scores"]
            for matchup_key, info in fetched_map.items():
              st.info(
                  f"🏟️ **{matchup_key}** | Status: `{info['status']}` | Score:"
                  f" {info['away_score']} - {info['home_score']}"
              )

        week_q = get_cached_weekly_questions(grade_week)
        real_grade_q = [
            q for q in week_q if q.get("question_number", 0) <= 10
        ]

        if not real_grade_q:
          st.warning("No questions found for this week.")
        else:
          with st.form("grade_form"):
            answers = {}
            for q in real_grade_q:
              default_val = (
                  q["winning_answer"]
                  if q["winning_answer"] in ["Yes", "No"]
                  else "Pending"
              )
              clean_prompt = (
                  q["question_text"].split(" | MATCHUP: ")[0]
                  if " | MATCHUP: " in q["question_text"]
                  else q["question_text"]
              )

              answers[q["id"]] = st.selectbox(
                  f"Q{q['question_number']}: {clean_prompt}",
                  ["Pending", "Yes", "No"],
                  index=["Pending", "Yes", "No"].index(default_val),
                  key=f"ans_{q['id']}",
              )

            st.markdown("---")
            st.markdown("#### 🏈 Touchdown Scorer Correct Picks")
            st.caption(
                "Select whether each player's Touchdown Scorer pick was correct"
                " (+5 bonus tokens) or incorrect."
            )

            td_picks_data = (
                supabase.table("touchdown_picks")
                .select("*")
                .eq("week_number", grade_week)
                .execute()
                .data
            )
            all_profiles = get_cached_profiles()
            profile_dict = {p["id"]: p["full_name"] for p in all_profiles}

            td_grading_results = {}
            if not td_picks_data:
              st.info("No Touchdown picks submitted for this week.")
            else:
              for td in td_picks_data:
                player_user_name = profile_dict.get(
                    td["user_id"], "Unknown Player"
                )
                current_is_correct = td.get("is_correct")

                if current_is_correct is None:
                  default_choice = "Pending"
                elif str(current_is_correct).lower() == "true":
                  default_choice = "Correct (+5 🪙)"
                else:
                  default_choice = "Incorrect (Miss)"

                col_p_name, col_p_sel = st.columns([2, 1])
                with col_p_name:
                  st.markdown(
                      f"**{player_user_name}**<br>Picked:"
                      f" *{td['player_name']}*",
                      unsafe_allow_html=True,
                  )
                with col_p_sel:
                  grade_choice = st.selectbox(
                      f"Grade {player_user_name}",
                      ["Pending", "Correct (+5 🪙)", "Incorrect (Miss)"],
                      index=[
                          "Pending",
                          "Correct (+5 🪙)",
                          "Incorrect (Miss)",
                      ].index(default_choice),
                      key=f"td_grade_{td['id']}",
                      label_visibility="collapsed",
                  )

                td_grading_results[td["id"]] = grade_choice

              st.divider()

            submit_grade_btn = st.form_submit_button(
                "Calculate & Process Payouts 🏆", type="primary"
            )

            if submit_grade_btn:
              if is_week_closed:
                st.error(
                    "This week is closed and cannot be graded again unless"
                    " reopened."
                )
              else:
                for q_id, ans in answers.items():
                  supabase.table("weekly_questions").update(
                      {"winning_answer": ans}
                  ).eq("id", q_id).execute()

                for td_id, choice in td_grading_results.items():
                  if choice == "Correct (+5 🪙)":
                    supabase.table("touchdown_picks").update(
                        {"is_correct": True}
                    ).eq("id", td_id).execute()
                  elif choice == "Incorrect (Miss)":
                    supabase.table("touchdown_picks").update(
                        {"is_correct": False}
                    ).eq("id", td_id).execute()
                  else:
                    supabase.table("touchdown_picks").update(
                        {"is_correct": None}
                    ).eq("id", td_id).execute()

                supabase.table("weekly_questions").delete().eq(
                    "week_number", grade_week
                ).eq("question_number", 96).execute()
                supabase.table("weekly_questions").insert({
                    "week_number": grade_week,
                    "question_number": 96,
                    "question_text": "WEEK CLOSED MARKER",
                    "winning_answer": "CLOSED",
                }).execute()

                recalculate_all_user_balances(supabase)

                st.cache_data.clear()
                st.balloons()
                st.success(
                    "Scores graded, payouts processed, and week successfully"
                    " closed!"
                )
                st.rerun()

      elif admin_sec == "Bulk Token Adjuster":
        st.subheader("👥 Bulk Player Token Adjuster & Reset Wizard")
        st.caption(
            "Select multiple players at once and apply a token adjustment or"
            " reset."
        )

        all_profiles_bulk = get_cached_profiles()

        if not all_profiles_bulk:
          st.info("No players found.")
        else:
          with st.form("bulk_token_form"):
            st.markdown("#### Select players")
            selected_user_ids = []

            for p in all_profiles_bulk:
              is_checked = st.checkbox(
                  f"**{p['full_name']}** (Current Balance: `{p['tokens']} 🪙` |"
                  f" Team: {p['favorite_team']})",
                  key=f"bulk_chk_{p['id']}",
              )
              if is_checked:
                selected_user_ids.append(p["id"])

            st.divider()
            st.markdown("#### Action to Apply")
            col_ba1, col_ba2 = st.columns(2)
            with col_ba1:
              action_type = st.selectbox(
                  "Operation",
                  ["Add Tokens", "Subtract Tokens", "Set Exact Token Balance"],
              )
            with col_ba2:
              token_amount_val = st.number_input(
                  "Token Value Amount", min_value=0, value=5, step=1
              )

            submit_bulk = st.form_submit_button(
                "Apply Bulk Adjustment ⚡", type="primary"
            )

            if submit_bulk:
              if not selected_user_ids:
                st.warning("Please check off at least one player above.")
              else:
                for u_id in selected_user_ids:
                  p_curr = next(
                      (p["tokens"] for p in all_profiles_bulk if p["id"] == u_id),
                      0,
                  )

                  if action_type == "Add Tokens":
                    new_bal = p_curr + token_amount_val
                  elif action_type == "Subtract Tokens":
                    new_bal = max(0, p_curr - token_amount_val)
                  else:
                    new_bal = token_amount_val

                  supabase.table("profiles").update({"tokens": new_bal}).eq(
                      "id", u_id
                  ).execute()

                st.cache_data.clear()
                st.balloons()
                st.success(
                    f"Successfully updated tokens for {len(selected_user_ids)}"
                    " players!"
                )
                st.rerun()

      elif admin_sec == "Export League Data (CSV)":
        st.subheader("📥 Export League Data to CSV")
        st.caption("Download full database dumps for Excel or record archives.")

        col_exp1, col_exp2 = st.columns(2)

        with col_exp1:
          bets_data = supabase.table("user_bets").select("*").execute().data
          if bets_data:
            df_bets = pd.DataFrame(bets_data)
            st.download_button(
                label="Download All User Bets (CSV)",
                data=df_bets.to_csv(index=False),
                file_name="touchdown_tokens_all_bets.csv",
                mime="text/csv",
            )

        with col_exp2:
          users_data = get_cached_profiles()
          if users_data:
            df_users = pd.DataFrame(users_data)[
                ["full_name", "tokens", "favorite_team", "bio"]
            ]
            st.download_button(
                label="Download Standings & Tokens (CSV)",
                data=df_users.to_csv(index=False),
                file_name="touchdown_tokens_standings.csv",
                mime="text/csv",
            )

      elif admin_sec == "League Chat Announcement":
        st.subheader("📢 Pre-Formatted League Announcement Generator")
        st.caption(
            "Copy and paste this message directly into your WhatsApp or group"
            " chat!"
        )

        ann_week = st.number_input(
            "Week Number", min_value=1, max_value=24, step=1, key="admin_ann_week"
        )

        graded_q_badge_ann = (
            supabase.table("weekly_questions")
            .select("week_number")
            .neq("week_number", 999)
            .neq("week_number", 998)
            .neq("week_number", 997)
            .neq("week_number", 96)
            .neq("winning_answer", "Pending")
            .neq("winning_answer", "LOCKED")
            .order("week_number", desc=True)
            .execute()
            .data
        )

        top_winner_str = "TBD"
        biggest_loser_str = "TBD"

        if graded_q_badge_ann:
          ann_graded_w = graded_q_badge_ann[0]["week_number"]
          w_bets = (
              supabase.table("user_bets")
              .select("*, weekly_questions(winning_answer)")
              .eq("week_number", ann_graded_w)
              .execute()
              .data
          )
          w_tds = (
              supabase.table("touchdown_picks")
              .select("*")
              .eq("week_number", ann_graded_w)
              .eq("is_correct", True)
              .execute()
              .data
          )

          u_net = {}
          for b in w_bets:
            u = b["user_id"]
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if u not in u_net:
              u_net[u] = 0
            if w_ans in ["Yes", "No"]:
              if b["pick"] == w_ans:
                u_net[u] += b["wager_amount"]
              else:
                u_net[u] -= b["wager_amount"]
          for td in w_tds:
            u = td["user_id"]
            u_net[u] = u_net.get(u, 0) + 5

          if u_net:
            best_u_id = max(u_net, key=u_net.get)
            worst_u_id = min(u_net, key=u_net.get)

            b_prof = (
                supabase.table("profiles")
                .select("full_name")
                .eq("id", best_u_id)
                .single()
                .execute()
                .data
            )
            w_prof = (
                supabase.table("profiles")
                .select("full_name")
                .eq("id", worst_u_id)
                .single()
                .execute()
                .data
            )

            if b_prof and u_net[best_u_id] > 0:
              top_winner_str = f"{b_prof['full_name']} (+{u_net[best_u_id]} tokens)"
            if w_prof and u_net[worst_u_id] < 0:
              biggest_loser_str = (
                  f"{w_prof['full_name']} ({u_net[worst_u_id]} tokens)"
              )

        top_player_res = (
            supabase.table("profiles")
            .select("full_name, tokens")
            .order("tokens", desc=True)
            .limit(1)
            .execute()
            .data
        )
        leader_str = (
            f"{top_player_res[0]['full_name']}"
            f" ({top_player_res[0]['tokens']} Tokens)"
            if top_player_res
            else "TBD"
        )

        announcement_template = f"""🏈 *TOUCHDOWN TOKENS - WEEK {ann_week} IS LIVE!* 🏈

👑 *Current League Leader:* {leader_str}
🚀 *Biggest Winner Last Week:* {top_winner_str}
📉 *Wall Street Bets Award (Biggest Loss):* {biggest_loser_str}

⏰ *Kickoff Cutoff:* Sunday before 1st Kickoff

👉 Place your wagers and TD scorer pick now on Touchdown Tokens!
Good luck this week! 🔥"""

        st.code(announcement_template, language="markdown")

      elif admin_sec == "Archive & Reset Season":
        st.subheader("🧹 End-of-Season Hall of Fame Archive & Reset Utility")
        st.caption(
            "Archive final mini-league standings into the permanent Hall of"
            " Fame database and reset all player balances back to 10 tokens for"
            " a fresh pre-season launch."
        )
        st.warning(
            "⚠️ Action Warning: This will snapshot and save the current"
            " mini-league standings permanently to the database, then reset all"
            " user token totals to 10!"
        )

        season_label = st.text_input("Season Label", value="2026 Season")
        confirm_check = st.checkbox(
            "I confirm I wish to archive standings to the Hall of Fame and"
            " reset all user balances to 10 tokens."
        )

        if st.button(
            "Archive to Hall of Fame & Reset Balances Now 🔄",
            type="primary",
            disabled=not confirm_check,
        ):
          try:
            all_profiles = get_cached_profiles()

            all_leagues_res = (
                supabase.table("leagues")
                .select("id, league_name")
                .neq("id", "00000000-0000-0000-0000-000000000001")
                .execute()
                .data
            )

            if all_leagues_res:
              for l in all_leagues_res:
                l_id = l["id"]
                members_res = (
                    supabase.table("league_members")
                    .select("user_id")
                    .eq("league_id", l_id)
                    .execute()
                    .data
                )
                member_ids = (
                    {m["user_id"] for m in members_res}
                    if members_res
                    else set()
                )

                league_players = [
                    p for p in all_profiles if p["id"] in member_ids
                ]
                league_players_sorted = sorted(
                    league_players, key=lambda x: (-x["tokens"], x["full_name"])
                )

                supabase.table("archived_seasons").insert({
                    "league_id": l_id,
                    "season_label": season_label,
                    "standings_json": league_players_sorted,
                }).execute()

            for p in all_profiles:
              supabase.table("profiles").update({"tokens": 10}).eq(
                  "id", p["id"]
              ).execute()

            st.cache_data.clear()
            st.balloons()
            st.success(
                f"Successfully archived '{season_label}' to the mini-league Hall"
                " of Fame and reset all player balances to 10 tokens!"
            )
          except Exception as e:
            st.error(f"Error archiving and resetting season: {e}")

      elif admin_sec == "App Access Control":
        st.subheader("🔒 App Sign-In & Sign-Up Access Control")
        st.caption(
            "Independently lock down sign-in and sign-up gateways to restrict"
            " access separately."
        )

        lock_signin_toggle = st.toggle("Lock Sign-In Gate", value=is_signin_locked)
        lock_signup_toggle = st.toggle("Lock Sign-Up Gate", value=is_signup_locked)

        if st.button("Save Access Control Settings 🛡️", type="primary"):
          signin_status = "LOCKED" if lock_signin_toggle else "OPEN"
          supabase.table("weekly_questions").delete().eq(
              "week_number", 998
          ).execute()
          supabase.table("weekly_questions").insert({
              "week_number": 998,
              "question_number": 1,
              "question_text": "SIGNIN ACCESS LOCK",
              "winning_answer": signin_status,
          }).execute()

          signup_status = "LOCKED" if lock_signup_toggle else "OPEN"
          supabase.table("weekly_questions").delete().eq(
              "week_number", 997
          ).execute()
          supabase.table("weekly_questions").insert({
              "week_number": 997,
              "question_number": 1,
              "question_text": "SIGNUP ACCESS LOCK",
              "winning_answer": signup_status,
          }).execute()

          st.cache_data.clear()
          st.success(
              f"Access settings updated! Sign-In: {signin_status}, Sign-Up:"
              f" {signup_status}"
          )
          st.rerun()
