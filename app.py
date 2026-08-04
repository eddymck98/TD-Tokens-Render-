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

controller = CookieController()

resend.api_key = os.environ.get("RESEND_API_KEY") or st.secrets.get("RESEND_API_KEY", "")

PROFANITY_FILTER = ["damn", "hell", "crap", "shit", "fuck", "bitch", "asshole", "dick", "cunt", "bastard"]

def contains_profanity(text: str) -> bool:
    if not text: return False
    text_lower = text.lower()
    words = text_lower.split()
    return any(p in text_lower or p in words for p in PROFANITY_FILTER)

def send_verification_email(to_email, verification_link):
    try:
        html_content = f"""
        <div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                <div style="text-align: center; margin-bottom: 30px;">
                    <img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" alt="Logo" style="width: 180px; margin-bottom: 15px;" />
                    <h1 style="font-family: 'Bebas Neue', Arial, sans-serif; color: #fbbf24; font-size: 32px; letter-spacing: 2px; margin: 0;">TOUCHDOWN TOKENS</h1>
                    <p style="color: #93c5fd; font-size: 14px; letter-spacing: 3px; text-transform: uppercase; margin-top: 5px;">Weekly NFL Predictions & Wagers</p>
                </div>
                <h3 style="color: #ffffff; font-size: 20px; margin-bottom: 15px;">Welcome to the League, Fan! 🏈</h3>
                <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 25px;">
                    Thanks for registering an account with Touchdown Tokens. Authorise your email address below:
                </p>
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{verification_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; font-size: 16px; display: inline-block;">AUTHORISE EMAIL ADDRESS</a>
                </div>
            </div>
        </div>
        """
        resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [to_email], "subject": "🏈 Authorise Your Account", "html": html_content})
        return True
    except Exception as e:
        st.error(f"Failed to send verification email: {e}")
        return False

def get_supabase_client() -> Client:
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_KEY", "") or st.secrets.get("SUPABASE_KEY", ""))
    return st.session_state.supabase_client

supabase = get_supabase_client()

if "user" not in st.session_state or st.session_state.user is None:
    st.session_state.user = None
    try:
        saved_token = controller.get("td_tokens_session")
        if saved_token:
            user_response = supabase.auth.get_user(saved_token)
            if user_response and user_response.user:
                st.session_state.user = user_response.user
                try: supabase.auth.set_session(saved_token, saved_token)
                except: pass
        if st.session_state.user is None:
            curr_session = supabase.auth.get_session()
            if curr_session and curr_session.user:
                st.session_state.user = curr_session.user
    except: pass

if "form_refresh" not in st.session_state: st.session_state.form_refresh = 0
if "signup_success_email" not in st.session_state: st.session_state.signup_success_email = None

@st.cache_data(ttl=30)
def get_cached_profiles():
    res = supabase.table("profiles").select("id, full_name, tokens, favorite_team, is_admin, avatar_emoji, avatar_border, avatar_color, selected_title, featured_badges, unlocked_badges, favorite_player, bio, default_league_view, email_notifications, high_contrast_mode, reduced_motion").execute()
    return res.data if res.data else []

@st.cache_data(ttl=30)
def get_cached_weekly_questions(w_num):
    res = supabase.table("weekly_questions").select("*").eq("week_number", w_num).order("question_number").execute()
    return res.data if res.data else []

@st.cache_data(ttl=30)
def get_cached_all_weekly_questions_meta():
    res = supabase.table("weekly_questions").select("week_number, question_number, winning_answer").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute()
    return res.data if res.data else []

def get_true_global_token_balance(target_user_id):
    try:
        u_bets = supabase.table("user_bets").select("week_number, wager_amount, pick, weekly_questions(winning_answer)").eq("user_id", target_user_id).execute().data
        u_td = supabase.table("touchdown_picks").select("week_number, is_correct").eq("user_id", target_user_id).eq("is_correct", True).execute().data
        td_wins_map = {td["week_number"]: 5 for td in u_td}
        curr_tokens = 10
        if u_bets or td_wins_map:
            all_weeks = sorted(list(set([b["week_number"] for b in u_bets] + list(td_wins_map.keys()))))
            for w in all_weeks:
                for b in [b for b in u_bets if b["week_number"] == w]:
                    w_ans = b.get("weekly_questions", {}).get("winning_answer")
                    if w_ans in ["Yes", "No"]:
                        curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                if w in td_wins_map: curr_tokens += 5
        return max(0, curr_tokens)
    except: return 10

def recalculate_all_user_balances(supabase_client):
    admin_supabase = supabase_client
    try:
        sk, url = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", ""), os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
        if sk and url: admin_supabase = create_client(url, sk)
    except: pass

    all_users = admin_supabase.table("profiles").select("id, full_name, tokens").execute().data
    if not all_users: return

    closed_weeks = [r["week_number"] for r in admin_supabase.table("weekly_questions").select("week_number").eq("question_number", 96).eq("winning_answer", "CLOSED").execute().data]
    if not closed_weeks: return

    all_bets = admin_supabase.table("user_bets").select("*").execute().data
    all_questions = admin_supabase.table("weekly_questions").select("id, week_number, winning_answer").execute().data
    all_tds = admin_supabase.table("touchdown_picks").select("*").execute().data

    q_map = {q["id"]: str(q.get("winning_answer", "")).strip() for q in all_questions}
    user_net_changes = {u["id"]: 0 for u in all_users}

    for b in all_bets:
        if b.get("week_number") in closed_weeks:
            uid, q_id, wager, pick = b["user_id"], b.get("question_id"), int(b.get("wager_amount", 0)), str(b.get("pick", "")).strip().lower()
            w_ans = q_map.get(q_id, "").lower()
            if uid in user_net_changes and w_ans in ["yes", "no"]:
                user_net_changes[uid] += wager if pick == w_ans else -wager

    for td in all_tds:
        if td.get("week_number") in closed_weeks:
            uid = td["user_id"]
            if uid in user_net_changes and str(td.get("is_correct")).lower() == "true":
                user_net_changes[uid] += 5

    for uid, net_change in user_net_changes.items():
        admin_supabase.table("profiles").update({"tokens": max(0, 10 + net_change)}).eq("id", uid).execute()

@st.cache_data
def get_static_nfl_team_data():
    return {
        "🏈 Free Agent / Neutral": {"logo": "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true", "color": "#fbbf24", "stadium": "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Arizona Cardinals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png", "color": "#97233F", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Atlanta Falcons": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/atl.png", "color": "#A71930", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟣 Baltimore Ravens": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png", "color": "#241773", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Buffalo Bills": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png", "color": "#00338D", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Carolina Panthers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/car.png", "color": "#0085CA", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Chicago Bears": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/chi.png", "color": "#C83803", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Cincinnati Bengals": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cin.png", "color": "#FB4F14", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🟤 Cleveland Browns": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/cle.png", "color": "#FF3C00", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Dallas Cowboys": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png", "color": "#003594", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟠 Denver Broncos": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/den.png", "color": "#FB4F14", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Detroit Lions": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/det.png", "color": "#0076B6", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟢 Green Bay Packers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/gb.png", "color": "#203731", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Houston Texans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/hou.png", "color": "#03202F", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Indianapolis Colts": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ind.png", "color": "#002C5F", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🐆 Jacksonville Jaguars": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/jax.png", "color": "#006778", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Kansas City Chiefs": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png", "color": "#E31837", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🪙 Las Vegas Raiders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lv.png", "color": "#A5ACAF", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "⚡ Los Angeles Chargers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lac.png", "color": "#0080C6", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟡 Los Angeles Rams": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/lar.png", "color": "#003594", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🐬 Miami Dolphins": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png", "color": "#008E97", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟣 Minnesota Vikings": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/min.png", "color": "#4F2683", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔵 New England Patriots": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ne.png", "color": "#002244", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "⚜️ New Orleans Saints": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/no.png", "color": "#D3BC8D", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔵 New York Giants": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png", "color": "#0B2265", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🟢 New York Jets": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png", "color": "#125740", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🦅 Philadelphia Eagles": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png", "color": "#004C54", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🟡 Pittsburgh Steelers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png", "color": "#FFB612", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔴 San Francisco 49ers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png", "color": "#AA0000", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🟢 Seattle Seahawks": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png", "color": "#69BE28", "stadium": "https://images.unsplash.com/photo-1519766304817-4f37bda74a29?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Tampa Bay Buccaneers": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/tb.png", "color": "#D50A0A", "stadium": "https://images.unsplash.com/photo-1568605117036-5fe5e7bab0b7?auto=format&fit=crop&w=1920&q=80"},
        "🔵 Tennessee Titans": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/ten.png", "color": "#4B92DB", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
        "🔴 Washington Commanders": {"logo": "https://a.espncdn.com/i/teamlogos/nfl/500/was.png", "color": "#5A1414", "stadium": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1920&q=80"},
    }

NFL_TEAM_DATA = get_static_nfl_team_data()
NFL_TEAMS = list(NFL_TEAM_DATA.keys())
AVATAR_OPTIONS = ["🏈", "🐐", "⚡", "👑", "🎯", "💣", "💎", "🔥", "🛡️", "🚀", "🦁", "🐯", "🐻", "🦅", "🐺", "🦈", "🐉", "💀", "👽", "🤖", "⭐", "🏆", "🥇", "💪", "🎲", "🎩", "🍻", "🍕", "🍔", "💥", "🔮", "🃏", "🥷", "🧙‍♂️", "🧛‍♂️", "🧟‍♂️", "🦸‍♂️", "🦹‍♂️"]
BORDER_STYLE_OPTIONS = {"Classic Solid": "solid", "Double Neon Pulse": "double", "Dashed Gridiron": "dashed", "Stealth Dotted": "dotted", "Championship Ridge": "ridge", "Groove Outlined": "inset"}
AVAILABLE_TITLES = {
    "🏈 Gridiron Contender": {"badge": None, "req": "Default baseline title for all players."},
    "👑 League Champion": {"badge": "🏆 League Champion", "req": "Be crowned official end-of-season Champion."},
    "⭐ League Commissioner": {"badge": "⭐ League Commissioner", "req": "Administer a custom mini-league."},
    "🔮 The Oracle": {"badge": "🔮 Oracle of Delphi", "req": "Call a 5+ token wager correctly 4 weeks in a row."},
    "💰 Token Tycoon": {"badge": "🚀 Token Tycoon", "req": "Reach 30+ tokens."},
    "⚡ Gridiron Prophet": {"badge": "⚡ Gridiron Prophet", "req": "Correctly predict 5+ Touchdown Scorers."},
    "🎯 Sharp Shooter": {"badge": "🎯 Sniper", "req": "Correctly predict 3+ Touchdown Scorers."},
    "🏈 TD Specialist": {"badge": "🏈 TD Guru", "req": "Correctly predict 2+ Touchdown Scorers."},
    "📉 Bankrupt Gambler": {"badge": "📉 Down Bad", "req": "Reach 0 tokens."},
}
MASTER_BADGES = {
    "🚀 Token Tycoon": "Reach 30+ tokens", "🎯 High Roller": "Wager 10+ tokens on a single question",
    "⚡ Double Down Legend": "Wager 15+ tokens in a single week", "💣 All-In Maverick": "Wager 100% of remaining tokens",
    "🏈 TD Guru": "Correctly predict 2+ Touchdown Scorers", "🎯 Sniper": "Correctly predict 3+ Touchdown Scorers",
    "👑 Weekly High Scorer": "Win the most net tokens in a week", "🎯 Perfect 10/10": "Correctly answer all 10 scenarios",
    "🧊 Clutch Gene": "Win a scenario where 75%+ picked wrong", "🛡️ Iron Defender": "Submit bets for 5+ weeks without missing",
    "💰 Century Club": "Accumulate 100+ total tokens won", "📉 Wall Street Bets": "Take the largest token loss in a week",
    "📉 Down Bad": "Reach 0 tokens", "🏆 League Champion": "Be crowned official League Champion",
    "⭐ League Commissioner": "Administer a custom mini-league", "🔮 Oracle of Delphi": "Call 5+ token wager correctly 4 weeks straight",
    "🔥 Untouchable Run": "Gain 20+ net tokens in a single week", "⚡ Gridiron Prophet": "Correctly predict 5+ Touchdown Scorers",
    "💎 Diamond Hands": "Survive with <3 tokens and bounce back to 30+"
}

user_team_color, user_team_logo, user_stadium_bg = "#fbbf24", "https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true", "https://images.unsplash.com/photo-1566577739112-5180d4bf9390?auto=format&fit=crop&w=1920&q=80"

if st.session_state.user:
    try:
        res = supabase.table("profiles").select("favorite_team").eq("id", st.session_state.user.id).single().execute()
        if res.data:
            t_info = NFL_TEAM_DATA.get(res.data.get("favorite_team"), NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
            user_team_color, user_team_logo, user_stadium_bg = t_info["color"], t_info["logo"], t_info["stadium"]
    except: pass

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700&family=Teko:wght@500;700&display=swap');
    .stMainBlockContainer, div[data-testid="stMainBlockContainer"] {{ padding-top: 1rem !important; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}
    .stApp, div[data-testid="stAppViewContainer"] {{
        background: radial-gradient(circle at 50% 20%, rgba(15, 23, 42, 0.90), rgba(7, 13, 25, 0.99)), url('{user_team_logo}') center center / 28% no-repeat fixed, url('{user_stadium_bg}') center center / cover no-repeat fixed !important;
        color: #f8fafc !important; font-family: 'Inter', sans-serif !important;
    }}
    section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #030712 0%, #0b0f19 100%) !important; border-right: 3px solid {user_team_color} !important; box-shadow: 6px 0 30px rgba(0,0,0,0.7); }}
    a, a:visited, a:hover, a:active {{ color: #38bdf8 !important; text-decoration: underline !important; }}
    p, span, label, div[data-testid="stMarkdownContainer"] {{ color: #f8fafc !important; }}
    .nfl-header {{ text-align: center; padding: 0px 0 4px 0; margin-top: -25px; }}
    .nfl-subtitle {{ font-family: 'Teko', sans-serif; font-size: 24px; letter-spacing: 5px; color: #93c5fd; text-transform: uppercase; margin-top: -4px; }}
    .header-logo {{ width: 240px; filter: drop-shadow(0px 10px 22px {user_team_color}cc); border-radius: 12px; }}
    .sticky-balance-bar {{
        position: sticky; top: 0; z-index: 999; background: rgba(15, 23, 42, 0.94); border: 1px solid rgba(255, 255, 255, 0.12);
        border-bottom: 3px solid {user_team_color}; padding: 10px 22px; margin: 4px 0 20px 0; border-radius: 0 0 16px 16px;
        backdrop-filter: blur(16px); display: flex; justify-content: space-between; align-items: center; box-shadow: 0 10px 30px rgba(0,0,0,0.7);
    }}
    .big-token-card {{
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.88) 0%, rgba(6, 10, 18, 0.94) 100%); padding: 32px; border-radius: 20px;
        color: #ffffff !important; text-align: center; border: 1px solid rgba(255, 255, 255, 0.15); border-top: 3px solid {user_team_color};
        margin-bottom: 25px; backdrop-filter: blur(16px); box-shadow: 0 10px 35px rgba(0,0,0,0.5);
    }}
    .big-token-number {{ font-family: 'Bebas Neue', sans-serif; font-size: 78px; letter-spacing: 3px; margin: 0; color: {user_team_color} !important; text-shadow: 0px 6px 20px {user_team_color}99; }}
    .champion-card {{ background: linear-gradient(135deg, rgba(120, 53, 15, 0.92) 0%, rgba(245, 158, 11, 0.92) 100%); padding: 32px; border-radius: 18px; color: #ffffff !important; text-align: center; border-top: 4px solid #fbbf24; margin-bottom: 30px; }}
    .mvp-banner {{ background: linear-gradient(135deg, rgba(147, 51, 234, 0.90) 0%, rgba(30, 58, 138, 0.94) 100%); border-top: 3px solid #c084fc; padding: 22px; border-radius: 16px; margin-bottom: 22px; text-align: center; }}
    .trophy-card-unlocked {{ background: rgba(15, 23, 42, 0.94); border-left: 4px solid {user_team_color}; padding: 16px; border-radius: 14px; margin-bottom: 14px; }}
    .trophy-card-locked {{ background: rgba(15, 23, 42, 0.55); border: 1px dashed rgba(255, 255, 255, 0.18); padding: 16px; border-radius: 14px; margin-bottom: 14px; opacity: 0.55; }}
    .leaderboard-row {{ background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 6px 12px; margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between; }}
    .podium-rank-1 {{ border-left: 4px solid #fbbf24 !important; background: linear-gradient(135deg, rgba(251, 191, 36, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .podium-rank-2 {{ border-left: 4px solid #94a3b8 !important; background: linear-gradient(135deg, rgba(148, 163, 184, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .podium-rank-3 {{ border-left: 4px solid #b45309 !important; background: linear-gradient(135deg, rgba(180, 83, 9, 0.12) 0%, rgba(15, 23, 42, 0.90) 100%) !important; }}
    .stat-pill-container {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }}
    .stat-pill {{ background: rgba(30, 41, 59, 0.85); border-radius: 12px; padding: 0px 6px; font-size: 9px; font-weight: 600; color: #cbd5e1; display: inline-flex; align-items: center; gap: 3px; }}
    .vs-card, .timer-card, .rule-card {{ background: rgba(15, 23, 42, 0.90); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 3px solid {user_team_color}; padding: 22px; border-radius: 16px; margin-bottom: 22px; }}
    .matchup-team-title {{ font-family: 'Teko', sans-serif; font-size: 24px; letter-spacing: 1.5px; color: #fbbf24; text-transform: uppercase; }}
    .chat-bubble, .summary-box {{ background-color: rgba(15, 23, 42, 0.88); padding: 14px 18px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.1); }}
    .summary-box {{ border-left: 4px solid {user_team_color} !important; margin-top: 16px; }}
    .rule-step-num {{ font-family: 'Bebas Neue', sans-serif; font-size: 28px; color: {user_team_color}; letter-spacing: 2px; }}
    div.stButton > button[kind="primary"], div.stFormSubmitButton > button {{
        background: linear-gradient(135deg, {user_team_color} 0%, #d97706 100%) !important; color: #000000 !important;
        font-family: 'Teko', sans-serif !important; font-size: 25px !important; letter-spacing: 2px !important; text-transform: uppercase !important; border-radius: 12px !important; border: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)

st.markdown(f'<div class="nfl-header"><img src="https://github.com/eddymck98/TD-Tokens-Render-/blob/main/TD%20Tokens%207.png?raw=true" class="header-logo" alt="Logo" /><div class="nfl-subtitle">Weekly NFL Predictions & Wagers</div></div>', unsafe_allow_html=True)

def sync_and_get_user_badges(target_user_id, check_celebration=False):
    try:
        p_data = supabase.table("profiles").select("tokens, unlocked_badges").eq("id", target_user_id).single().execute().data
        if not p_data: return []
    except: return []

    toks = get_true_global_token_balance(target_user_id)
    existing_unlocked = p_data.get("unlocked_badges") if isinstance(p_data.get("unlocked_badges"), list) else []
    newly_earned = set(existing_unlocked)

    if supabase.table("leagues").select("id").eq("created_by", target_user_id).execute().data or p_data.get("is_admin"):
        newly_earned.add("⭐ League Commissioner")
    if toks >= 30: newly_earned.add("🚀 Token Tycoon")
    if toks == 0: newly_earned.add("📉 Down Bad")

    u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", target_user_id).execute().data
    u_td = supabase.table("touchdown_picks").select("*").eq("user_id", target_user_id).eq("is_correct", True).execute().data

    if any(b["wager_amount"] >= 10 for b in u_bets): newly_earned.add("🎯 High Roller")
    if len(u_td) >= 2: newly_earned.add("🏈 TD Guru")
    if len(u_td) >= 3: newly_earned.add("🎯 Sniper")
    if len(u_td) >= 5: newly_earned.add("⚡ Gridiron Prophet")

    weeks_played, total_lifetime_won, weekly_nets = set(), 0, {}
    for b in u_bets:
        w_num = b["week_number"]
        weeks_played.add(w_num)
        w_ans = b.get("weekly_questions", {}).get("winning_answer")
        if w_num not in weekly_nets: weekly_nets[w_num] = {"gains": 0, "losses": 0}
        if w_ans in ["Yes", "No"]:
            if b["pick"] == w_ans:
                total_lifetime_won += b["wager_amount"]
                weekly_nets[w_num]["gains"] += b["wager_amount"]
            else: weekly_nets[w_num]["losses"] += b["wager_amount"]

    for td in u_td:
        if td["week_number"] in weekly_nets: weekly_nets[td["week_number"]]["gains"] += 5

    sorted_weeks = sorted(list(weekly_nets.keys()))
    consec_oracle = 0
    for w in sorted_weeks:
        has_large_win = any(b["wager_amount"] >= 5 and b["pick"] == b.get("weekly_questions", {}).get("winning_answer") for b in u_bets if b["week_number"] == w)
        if has_large_win:
            consec_oracle += 1
            if consec_oracle >= 4: newly_earned.add("🔮 Oracle of Delphi")
        else: consec_oracle = 0

    for w, w_data in weekly_nets.items():
        if w_data["gains"] - w_data["losses"] >= 20: newly_earned.add("🔥 Untouchable Run")

    if toks >= 30:
        sim_tokens, ever_low = 10, False
        for w in sorted_weeks:
            if sim_tokens < 3: ever_low = True
            sim_tokens += weekly_nets[w]["gains"] - weekly_nets[w]["losses"]
        if ever_low: newly_earned.add("💎 Diamond Hands")

    if len(weeks_played) >= 5: newly_earned.add("🛡️ Iron Defender")
    if total_lifetime_won >= 100: newly_earned.add("💰 Century Club")

    graded_q = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).neq("winning_answer", "Pending").neq("winning_answer", "LOCKED").order("week_number", desc=True).execute().data
    if graded_q:
        latest_w = graded_q[0]["week_number"]
        all_latest_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("week_number", latest_w).execute().data
        user_gains, user_loss, user_correct = {}, {}, {}
        for b in all_latest_bets:
            u, w_ans = b["user_id"], b.get("weekly_questions", {}).get("winning_answer")
            if u not in user_gains: user_gains[u], user_loss[u], user_correct[u] = 0, 0, 0
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans: user_gains[u] += b["wager_amount"]; user_correct[u] += 1
                else: user_loss[u] += b["wager_amount"]
        if user_gains and max(user_gains.values(), default=-1) > 0 and max(user_gains, key=user_gains.get) == target_user_id: newly_earned.add("👑 Weekly High Scorer")
        if user_loss and max(user_loss.values(), default=-1) > 0 and max(user_loss, key=user_loss.get) == target_user_id: newly_earned.add("📉 Wall Street Bets")
        if user_correct.get(target_user_id, 0) == 10: newly_earned.add("🎯 Perfect 10/10")

    final_badges_list = list(newly_earned)
    if set(final_badges_list) != set(existing_unlocked):
        try: supabase.table("profiles").update({"unlocked_badges": final_badges_list}).eq("id", target_user_id).execute()
        except: pass

    if check_celebration and target_user_id == st.session_state.user.id:
        cache_key = f"seen_badges_{target_user_id}"
        if cache_key not in st.session_state: st.session_state[cache_key] = final_badges_list
        else:
            newly_detected = [b for b in final_badges_list if b not in st.session_state[cache_key]]
            if newly_detected:
                st.balloons()
                for nb in newly_detected: st.toast(f"🏆 NEW TROPHY UNLOCKED: {nb}!", icon="🎉")
                st.session_state[cache_key] = final_badges_list

    return final_badges_list

@st.cache_data(ttl=60)
def get_earned_title(target_user_id):
    try:
        prof_res = supabase.table("profiles").select("selected_title").eq("id", target_user_id).single().execute().data
        if prof_res and prof_res.get("selected_title") in AVAILABLE_TITLES: return prof_res.get("selected_title")
    except: pass
    user_badges = sync_and_get_user_badges(target_user_id)
    for title, info in AVAILABLE_TITLES.items():
        if info["badge"] and info["badge"] in user_badges: return title
    return "🏈 Gridiron Contender"

@st.cache_data(ttl=60)
def calculate_nemesis(target_user_id, allowed_peer_ids=None):
    try:
        user_bets = supabase.table("user_bets").select("week_number, question_id, pick").eq("user_id", target_user_id).execute().data
        if not user_bets: return "None Yet", 0
        user_picks_map = {(b["week_number"], b["question_id"]): b["pick"] for b in user_bets}
        rival_disagreements = {}
        for (w_num, q_id), u_pick in user_picks_map.items():
            qb = supabase.table("user_bets").select("user_id, pick, weekly_questions(winning_answer)").eq("week_number", w_num).eq("question_id", q_id).neq("user_id", target_user_id)
            if allowed_peer_ids is not None:
                if not allowed_peer_ids: continue
                qb = qb.in_("user_id", list(allowed_peer_ids))
            for ob in qb.execute().data:
                rival_id, rival_pick, winning_ans = ob["user_id"], ob["pick"], ob.get("weekly_questions", {}).get("winning_answer")
                if rival_pick != u_pick and winning_ans in ["Yes", "No"] and rival_pick == winning_ans:
                    rival_disagreements[rival_id] = rival_disagreements.get(rival_id, 0) + 1
        if not rival_disagreements: return "None Yet", 0
        nemesis_id = max(rival_disagreements, key=rival_disagreements.get)
        nemesis_prof = supabase.table("profiles").select("full_name").eq("id", nemesis_id).single().execute().data
        return (nemesis_prof.get("full_name", "Unknown Rival") if nemesis_prof else "Unknown Rival"), rival_disagreements[nemesis_id]
    except: return "None Yet", 0

@st.cache_data(ttl=60)
def calculate_streak(target_user_id):
    try:
        u_bets = supabase.table("user_bets").select("week_number, pick, weekly_questions(winning_answer)").eq("user_id", target_user_id).order("week_number", desc=True).execute().data
        if not u_bets: return "0W"
        streak = 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                if b["pick"] == w_ans: streak += 1
                else: break
        return f"{streak}W" if streak > 0 else "0W"
    except: return "0W"

@st.cache_data(ttl=60)
def get_cached_leaderboard_stats(allowed_peer_ids=None):
    leader_res, stats = get_cached_profiles(), []
    if not leader_res: return stats
    for p in leader_res:
        if allowed_peer_ids is not None and p["id"] not in allowed_peer_ids: continue
        true_toks = get_true_global_token_balance(p["id"])
        td_count = len(supabase.table("touchdown_picks").select("*").eq("user_id", p["id"]).eq("is_correct", True).execute().data or [])
        u_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("user_id", p["id"]).execute().data
        wins, total_graded = 0, 0
        for b in u_bets:
            w_ans = b.get("weekly_questions", {}).get("winning_answer")
            if w_ans in ["Yes", "No"]:
                total_graded += 1
                if b["pick"] == w_ans: wins += 1
        win_rate = int((wins / total_graded) * 100) if total_graded > 0 else 0
        nem_name, nem_score = calculate_nemesis(p["id"], allowed_peer_ids=allowed_peer_ids)
        stats.append({**p, "tokens": true_toks, "correct_tds": td_count, "win_rate": win_rate, "total_bets": total_graded, "nemesis_name": nem_name, "nemesis_score": nem_score, "streak": calculate_streak(p["id"])})
    return sorted(stats, key=lambda x: (-x["tokens"], -x["correct_tds"], x["full_name"]))

is_signin_locked, is_signup_locked = False, False
try:
    s_lock = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 998).execute().data
    is_signin_locked = s_lock and s_lock[0]["winning_answer"] == "LOCKED"
except: pass

try:
    su_lock = supabase.table("weekly_questions").select("winning_answer").eq("week_number", 997).execute().data
    is_signup_locked = su_lock and su_lock[0]["winning_answer"] == "LOCKED"
except: pass

# ==========================================
# 1. LOGIN & SIGNUP SCREEN WITH RESEND EMAIL
# ==========================================
if st.session_state.user is None:
    st.title("Touchdown Tokens")
    if st.session_state.get("signup_success_email"):
        success_email_val = st.session_state["signup_success_email"]
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 35px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); margin-top: 20px;">
            <h2 style="color: #fbbf24; font-family: 'Bebas Neue', Arial, sans-serif; font-size: 36px; letter-spacing: 2px; margin-bottom: 10px;">WELCOME TO THE LEAGUE! 🏈</h2>
            <p style="color: #cbd5e1; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">We have successfully created your account and sent a verification email to <b style="color: #38bdf8;">{success_email_val}</b>.</p>
        </div>""", unsafe_allow_html=True)
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Proceed to Log In 🔒", type="primary"): st.session_state.signup_success_email = None; st.rerun()
        with c2:
            if st.button("Sign Up Another Account 📝"): st.session_state.signup_success_email = None; st.rerun()
    else:
        tab_login, tab_signup = st.tabs(["🔒 Log In", "📝 Sign Up"])
        with tab_login:
            st.subheader("Login to Your Account")
            if is_signin_locked: st.error("🔒 **SIGN-IN LOCKED:** The Admin has temporarily disabled log-ins.")
            else:
                login_email, login_password = st.text_input("Email", key="login_email"), st.text_input("Password", type="password", key="login_password")
                if st.button("Login"):
                    if login_email and login_password:
                        try:
                            auth_response = supabase.auth.sign_in_with_password({"email": login_email, "password": login_password})
                            user = auth_response.user
                            if user and user.email_confirmed_at:
                                st.session_state["user"] = user
                                if auth_response.session and auth_response.session.access_token:
                                    controller.set("td_tokens_session", auth_response.session.access_token, max_age=2592000)
                                st.success("Successfully logged in!")
                                st.rerun()
                            else:
                                supabase.auth.sign_out()
                                st.error("Please authorise your email first before logging in.")
                        except: st.error("Invalid login credentials or unverified account.")
                    else: st.warning("Please enter both email and password.")

                st.write("")
                with st.expander("🔑 Forgot Password?"):
                    reset_email = st.text_input("Your Account Email", key="reset_email_input")
                    if st.button("Send Reset Link"):
                        if reset_email:
                            try:
                                admin_supabase = supabase
                                service_key, url = os.environ.get("SUPABASE_SERVICE_KEY", "") or st.secrets.get("SUPABASE_SERVICE_KEY", ""), os.environ.get("SUPABASE_URL", "") or st.secrets.get("SUPABASE_URL", "")
                                if service_key and url: admin_supabase = create_client(url, service_key)
                                response = admin_supabase.auth.admin.generate_link({"type": "recovery", "email": reset_email.strip()})
                                if response and hasattr(response, "properties"):
                                    recovery_link = response.properties.action_link
                                    html_content = f"""<div style="background-color: #0b0f19; padding: 30px; font-family: 'Inter', Arial, sans-serif; color: #f8fafc;"><div style="max-width: 600px; margin: 0 auto; background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(255, 255, 255, 0.12); border-top: 4px solid #fbbf24; border-radius: 16px; padding: 40px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);"><h3 style="color: #ffffff; font-size: 20px;">Reset Your Password 🔑</h3><div style="text-align: center; margin: 35px 0;"><a href="{recovery_link}" style="background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); color: #000000; padding: 14px 28px; text-decoration: none; border-radius: 12px; font-weight: bold; display: inline-block;">RESET PASSWORD</a></div></div></div>"""
                                    resend.Emails.send({"from": "Touchdown Tokens <noreply@auth.tdtokens.co.uk>", "to": [reset_email.strip()], "subject": "🔑 Reset Your Password", "html": html_content})
                                    st.success("Password reset email sent via Resend!")
                                else: st.error("Could not generate recovery link.")
                            except Exception as e: st.error(f"Error sending password reset email: {e}")
                        else: st.warning("Please enter your email address.")

        with tab_signup:
            st.subheader("Create an Account")
            if is_signup_locked: st.error("🔒 **SIGN-UP LOCKED:** Registrations are temporarily disabled.")
            else:
                st.caption("New players start with 10 free tokens!")
                c1, c2 = st.columns(2)
                with c1: reg_first_name = st.text_input("First Name", key="reg_first_name")
                with c2: reg_surname = st.text_input("Surname", key="reg_surname")
                signup_email, signup_password = st.text_input("Email Address", key="signup_email"), st.text_input("Password (min 6 chars)", type="password", key="signup_password")
                
                with st.expander("📖 View Touchdown Tokens Terms of Service & User Agreement"):
                    st.markdown("**TOUCHDOWN TOKENS — TERMS OF SERVICE & USER AGREEMENT**\n\n1. Virtual Currency: Zero cash value, recreational purpose only.\n2. Eligibility: One account per user.\n3. Deadlines: 15 minutes before kickoff.")
                tc_accepted = st.checkbox("I agree to the Touchdown Tokens Terms of Service & User Agreement", key="reg_tc_checkbox")

                if st.button("Sign Up"):
                    if not reg_first_name.strip() or not reg_surname.strip() or not signup_email.strip(): st.warning("Please fill out all required fields.")
                    elif not tc_accepted: st.warning("You must accept the Terms of Service.")
                    else:
                        combined_full_name = f"{reg_first_name.strip()} {reg_surname.strip()}"
                        if contains_profanity(combined_full_name): st.error("⚠️ Your name contains restricted language.")
                        else:
                            try:
                                response = supabase.auth.sign_up({"email": signup_email.strip(), "password": signup_password})
                                if response.user:
                                    new_uid = response.user.id
                                    supabase.table("profiles").insert({
                                        "id": new_uid, "email": signup_email.strip(), "full_name": combined_full_name, "tokens": 10,
                                        "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!",
                                        "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid",
                                        "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender",
                                        "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True,
                                        "high_contrast_mode": False, "reduced_motion": False
                                    }).execute()
                                    try: supabase.table("league_members").insert({"league_id": "00000000-0000-0000-0000-000000000001", "user_id": new_uid}).execute()
                                    except: pass
                                    send_verification_email(signup_email.strip(), "https://tdtokens.co.uk")
                                    try: supabase.auth.sign_out()
                                    except: pass
                                    st.session_state.signup_success_email = signup_email.strip()
                                    st.rerun()
                                else: st.error("Sign up failed.")
                            except Exception as e: st.error(f"Error: {e}")

# ==========================================
# 2. MAIN LOGGED-IN GAME PORTAL
# ==========================================
else:
    user_id = st.session_state.user.id
    try: profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute().data
    except: profile = None

    if not profile:
        try:
            fallback_name = st.session_state.user.email.split("@")[0].capitalize()
            supabase.table("profiles").insert({
                "id": user_id, "email": st.session_state.user.email, "full_name": fallback_name, "tokens": 10,
                "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!",
                "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid",
                "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender",
                "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True,
                "high_contrast_mode": False, "reduced_motion": False
            }).execute()
            try: supabase.table("league_members").insert({"league_id": "00000000-0000-0000-0000-000000000001", "user_id": user_id}).execute()
            except: pass
            profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute().data
        except:
            profile = {"id": user_id, "full_name": "Player", "tokens": 10, "is_admin": False, "favorite_team": "🏈 Free Agent / Neutral", "bio": "Ready for Kickoff!", "avatar_emoji": "🏈", "featured_badges": [], "unlocked_badges": [], "avatar_border": "solid", "favorite_player": "", "avatar_color": "#1e3a8a", "selected_title": "🏈 Gridiron Contender", "default_league_view": "00000000-0000-0000-0000-000000000001", "email_notifications": True, "high_contrast_mode": False, "reduced_motion": False}

    user_avatar, user_team = profile.get("avatar_emoji", "🏈"), profile.get("favorite_team", "🏈 Free Agent / Neutral")
    team_data = NFL_TEAM_DATA.get(user_team, NFL_TEAM_DATA["🏈 Free Agent / Neutral"])
    sync_and_get_user_badges(user_id, check_celebration=True)

    my_administered_leagues = supabase.table("leagues").select("id, league_name, invite_code, league_password").eq("created_by", user_id).execute().data
    is_any_league_admin = bool(my_administered_leagues) or profile.get("is_admin", False)

    # --- SIDEBAR ---
    st.sidebar.markdown(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 12px; padding: 6px 0;">
            <div style="border: 3px {profile.get('avatar_border', 'solid')} {user_team_color}; border-radius: 12px; padding: 6px 10px; background: {profile.get('avatar_color', '#1e3a8a')};">
                <span style="font-size: 34px;">{user_avatar}</span>
            </div>
            <div>
                <b style="font-size: 19px; color: #ffffff;">{profile['full_name']}</b>
                <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">{get_earned_title(user_id)}</div>
                <div style="font-size: 12px; color: #94a3b8;">{user_team}</div>
            </div>
        </div>""", unsafe_allow_html=True)
    st.sidebar.image(team_data["logo"], width=55)

    if profile.get("favorite_player"):
        st.sidebar.markdown(f"<div style='font-size:14px; color:#38bdf8; margin-top:-4px;'>⭐ Fav Player: <b>{profile.get('favorite_player')}</b></div>", unsafe_allow_html=True)

    available_weeks = sorted(list(set([r["week_number"] for r in supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data or []])))
    
    true_global_tokens_sidebar = get_true_global_token_balance(user_id)
    active_tokens_display = true_global_tokens_sidebar
    if available_weeks:
        latest_w_active = available_weeks[-1]
        is_latest_graded = False
        latest_week_status = supabase.table("weekly_questions").select("winning_answer").eq("week_number", latest_w_active).eq("question_number", 96).execute().data
        if latest_week_status and latest_week_status[0]["winning_answer"] == "CLOSED": is_latest_graded = True
        else:
            w_qs_check = supabase.table("weekly_questions").select("winning_answer").eq("week_number", latest_w_active).neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).execute().data
            if w_qs_check and all(q["winning_answer"] in ["Yes", "No"] for q in w_qs_check): is_latest_graded = True
        if not is_latest_graded:
            user_active_bets = supabase.table("user_bets").select("wager_amount").eq("user_id", user_id).eq("week_number", latest_w_active).execute().data
            total_wagered_active = sum([b["wager_amount"] for b in user_active_bets]) if user_active_bets else 0
            active_tokens_display = max(0, true_global_tokens_sidebar - total_wagered_active)

    st.sidebar.metric(label="Available Tokens", value=f"{active_tokens_display} 🪙")
    if profile.get("is_admin"): st.sidebar.success("👑 System Admin Active")
    elif is_any_league_admin: st.sidebar.info("⭐ League Commissioner Active")

    st.sidebar.divider()
    if st.sidebar.button("Log Out"):
        try: supabase.auth.sign_out()
        except: pass
        controller.remove("td_tokens_session")
        st.session_state.user = None
        if "supabase_client" in st.session_state: del st.session_state["supabase_client"]
        st.rerun()

    # --- STICKY HEADER ---
    st.markdown(f"""
        <div class="sticky-balance-bar">
            <div style="display: flex; align-items: center; gap: 14px;">
                <div style="border: 3px {profile.get('avatar_border', 'solid')} {user_team_color}; border-radius: 10px; padding: 3px 8px; background: {profile.get('avatar_color', '#1e3a8a')};">
                    <span style="font-size: 26px;">{user_avatar}</span>
                </div>
                <div>
                    <b style="font-size: 16px; color: #ffffff;">{profile['full_name']}</b> <span style="font-size:11px; color:#38bdf8; margin-left:6px;">({get_earned_title(user_id)})</span>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">{user_team}</div>
                </div>
            </div>
            <div style="text-align: right;">
                <span style="font-family: 'Bebas Neue'; font-size: 26px; color: {user_team_color};">{active_tokens_display} 🪙</span>
                <div style="font-size: 10px; color: #94a3b8; text-transform: uppercase;">Available Tokens</div>
            </div>
        </div>""", unsafe_allow_html=True)

    if profile.get("is_admin") and is_any_league_admin:
        tabs = st.tabs(["🏠 Home", "👤 Profile", "📖 Rules", "🎯 Bets", "📜 History", "🛡️ Leagues", "⭐ Commish", "⚙️ Settings", "🛠️ Admin"])
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_league_admin, tab_settings, tab_admin = tabs
    elif profile.get("is_admin"):
        tabs = st.tabs(["🏠 Home", "👤 Profile", "📖 Rules", "🎯 Bets", "📜 History", "🛡️ Leagues", "⚙️ Settings", "🛠️ Admin"])
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_settings, tab_admin = tabs
    elif is_any_league_admin:
        tabs = st.tabs(["🏠 Home", "👤 Profile", "📖 Rules", "🎯 Bets", "📜 History", "🛡️ Leagues", "⭐ Commish", "⚙️ Settings"])
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_league_admin, tab_settings = tabs
    else:
        tabs = st.tabs(["🏠 Home", "👤 Profile", "📖 Rules", "🎯 Bets", "📜 History", "🛡️ Leagues", "⚙️ Settings"])
        tab_home, tab_profile, tab_rules, tab_bet, tab_history, tab_leagues, tab_settings = tabs

    # ------------------------------------------
    # TAB 0: HOME
    # ------------------------------------------
    with tab_home:
        st.markdown(f"## Welcome back, {profile['full_name']}! 👋")
        st.markdown(f"""
            <div class="big-token-card">
                <div style="font-size: 18px; letter-spacing: 2px; text-transform: uppercase; color: #93c5fd;">Available Balance</div>
                <div class="big-token-number">{active_tokens_display} 🪙</div>
                <div style="font-size: 16px; color: #cbd5e1;">True Global Bank: {true_global_tokens_sidebar} 🪙 (Active Wagers Deducted)</div>
            </div>""", unsafe_allow_html=True)

        st.subheader("👁️ Your Current Weekly Picks & Share Hub")
        if not available_weeks: st.info("No active weeks available.")
        else:
            view_week = st.selectbox("Select Week to View", available_weeks, index=len(available_weeks) - 1, key="home_view_current_week_sel")
            curr_user_bets = supabase.table("user_bets").select("*, weekly_questions(question_number, question_text)").eq("user_id", user_id).eq("week_number", view_week).order("question_id").execute().data
            curr_user_td = supabase.table("touchdown_picks").select("player_name").eq("user_id", user_id).eq("week_number", view_week).execute().data

            if not curr_user_bets and not curr_user_td: st.warning(f"You haven't submitted any picks for Week {view_week} yet!")
            else:
                share_lines = [f"🏈 *{profile['full_name']} - Week {view_week} Lock-Ins* 🏈"]
                for b in curr_user_bets:
                    q_num = b.get("weekly_questions", {}).get("question_number", "?")
                    q_txt = b.get("weekly_questions", {}).get("question_text", "").split(" | MATCHUP: ")[0]
                    st.markdown(f'<div class="summary-box"><b>Q{q_num}: {q_txt}</b><br>• Your Pick: <b style="color:{user_team_color};">{b["pick"]}</b> | Wager: <b>{b["wager_amount"]} 🪙</b></div>', unsafe_allow_html=True)
                    share_lines.append(f"Q{q_num}: {b['pick']} ({b['wager_amount']} tokens)")

                td_name = curr_user_td[0]["player_name"] if curr_user_td else "None"
                st.markdown(f'<div class="summary-box" style="border-left-color: #38bdf8 !important;"><b>🏈 Touchdown Scorer Bonus Pick:</b><br>• Player: <b style="color:#38bdf8;">{td_name}</b></div>', unsafe_allow_html=True)
                share_lines.append(f"TD Scorer Pick: {td_name}")

                st.write("")
                st.subheader("📋 Group Chat Share Text")
                st.code("\n".join(share_lines), language="markdown")

        graded_q_badge = supabase.table("weekly_questions").select("week_number").neq("week_number", 999).neq("week_number", 998).neq("week_number", 997).neq("week_number", 96).neq("winning_answer", "Pending").neq("winning_answer", "LOCKED").order("week_number", desc=True).execute().data
        if graded_q_badge:
            latest_mvp_week = graded_q_badge[0]["week_number"]
            mvp_bets = supabase.table("user_bets").select("*, weekly_questions(winning_answer)").eq("week_number", latest_mvp_week).execute().data
            mvp_tds = supabase.table("touchdown_picks").select("*").eq("week_number", latest_mvp_week).eq("is_correct", True).execute().data
            user_weekly_net = {}
            for b in mvp_bets:
                u, w_ans = b["user_id"], b.get("weekly_questions", {}).get("winning_answer")
                if u not in user_weekly_net: user_weekly_net[u] = 0
                if w_ans in ["Yes", "No"]: user_weekly_net[u] += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
            for td in mvp_tds: user_weekly_net[td["user_id"]] = user_weekly_net.get(td["user_id"], 0) + 5

            if user_weekly_net and max(user_weekly_net.values(), default=-1) > 0:
                top_mvp_id = max(user_weekly_net, key=user_weekly_net.get)
                mvp_profile = supabase.table("profiles").select("full_name, avatar_emoji, favorite_team").eq("id", top_mvp_id).single().execute().data
                if mvp_profile:
                    st.markdown(f"""
                        <div class="mvp-banner">
                            <div style="font-size: 16px; letter-spacing: 2px; text-transform: uppercase; color: #f3e8ff;">🔥 Week {latest_mvp_week} League MVP 🔥</div>
                            <div style="font-size: 36px; font-weight: 900; margin: 5px 0; color: #ffffff;">{mvp_profile.get('avatar_emoji', '🏈')} {mvp_profile['full_name']}</div>
                            <div style="font-size: 16px; color: #d8b4fe;">Dominated the slate with <b>+{user_weekly_net[top_mvp_id]} Net Tokens</b>! 🚀</div>
                        </div>""", unsafe_allow_html=True)

        st.divider()
        st.subheader("📊 Token History Graph")
        history_bets_all = supabase.table("user_bets").select("week_number, wager_amount, pick, weekly_questions(winning_answer)").eq("user_id", user_id).execute().data
        all_td_history = supabase.table("touchdown_picks").select("week_number, is_correct").eq("user_id", user_id).eq("is_correct", True).execute().data
        td_wins_map = {td["week_number"]: 5 for td in all_td_history}

        if history_bets_all or td_wins_map:
            week_tokens, curr_tokens = {0: 10}, 10
            for w in sorted(list(set([b["week_number"] for b in history_bets_all] + list(td_wins_map.keys())))):
                for b in [b for b in history_bets_all if b["week_number"] == w]:
                    w_ans = b.get("weekly_questions", {}).get("winning_answer")
                    if w_ans in ["Yes", "No"]: curr_tokens += b["wager_amount"] if b["pick"] == w_ans else -b["wager_amount"]
                if w in td_wins_map: curr_tokens += 5
                week_tokens[w] = max(0, curr_tokens)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[f"Week {w}" if w > 0 else "Start" for w in week_tokens.keys()], y=list(week_tokens.values()), mode="lines+markers", line=dict(color=user_team_color, width=4, shape="spline"), fill="tozeroy"))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15, 23, 42, 0.75)", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("No token history data available yet.")

    # ------------------------------------------
    # TAB 1: PROFILE & TROPHY CABINET
    # ------------------------------------------
    with tab_profile:
        st.header("👤 Profile & Customization Hub")
        curr_team = profile.get("favorite_team", "🏈 Free Agent / Neutral")
        
        with st.form("profile_customization_form"):
            new_display_name = st.text_input("Display Name", value=profile.get("full_name", ""))
            new_team = st.selectbox("Favorite NFL Team", NFL_TEAMS, index=NFL_TEAMS.index(curr_team) if curr_team in NFL_TEAMS else 0)
            
            user_badges_for_titles = sync_and_get_user_badges(user_id)
            unlocked_title_options = [t for t, info in AVAILABLE_TITLES.items() if info["badge"] is None or info["badge"] in user_badges_for_titles]
            curr_selected_title = profile.get("selected_title", "🏈 Gridiron Contender")
            
            c1, c2 = st.columns(2)
            with c1: new_title = st.selectbox("Active Nametag Title", unlocked_title_options, index=unlocked_title_options.index(curr_selected_title) if curr_selected_title in unlocked_title_options else 0)
            with c2: new_avatar = st.selectbox("Avatar Emoji", AVATAR_OPTIONS, index=AVATAR_OPTIONS.index(profile.get("avatar_emoji", "🏈")) if profile.get("avatar_emoji", "🏈") in AVATAR_OPTIONS else 0)

            c3, c4 = st.columns(2)
            with c3: new_border = BORDER_STYLE_OPTIONS[st.selectbox("Avatar Border", list(BORDER_STYLE_OPTIONS.keys()))]
            with c4: new_av_color = st.color_picker("Avatar Box Color", value=profile.get("avatar_color", "#1e3a8a"))

            new_fav_player = st.text_input("Favorite NFL Player", value=profile.get("favorite_player", ""))
            new_bio = st.text_input("Profile Bio", value=profile.get("bio", "Ready for Kickoff!"), max_chars=100)

            if st.form_submit_button("Save Profile Settings 💾", type="primary"):
                if not new_display_name.strip(): st.error("Display Name cannot be blank.")
                elif contains_profanity(new_display_name) or contains_profanity(new_fav_player) or contains_profanity(new_bio): st.error("⚠️ Restricted language detected.")
                else:
                    supabase.table("profiles").update({"full_name": new_display_name.strip(), "favorite_team": new_team, "selected_title": new_title, "avatar_emoji": new_avatar, "avatar_border": new_border, "avatar_color": new_av_color, "favorite_player": new_fav_player.strip(), "bio": new_bio.strip()}).eq("id", user_id).execute()
                    st.success("Profile updated successfully!")
                    st.rerun()

        st.divider()
        st.subheader("⭐ Featured Badge Showcase")
        unlocked_badges = sync_and_get_user_badges(user_id)
        with st.form("featured_badges_form"):
            selected_featured = st.multiselect("Select up to 3 Badges", options=unlocked_badges, default=[b for b in (profile.get("featured_badges") or []) if b in unlocked_badges], max_selections=3)
            if st.form_submit_button("Save Featured Badges 🌟", type="primary"):
                supabase.table("profiles").update({"featured_badges": selected_featured}).eq("id", user_id).execute()
                st.success("Featured badges updated successfully!")
                st.rerun()

        st.divider()
        st.subheader("🏆 Virtual Trophy Cabinet")
        all_league_profiles = get_cached_profiles()
        selected_player = next((p for p in all_league_profiles if p["full_name"] == st.selectbox("Select Player Trophy Showcase", [p["full_name"] for p in all_league_profiles], key="trophy_player_select")), profile)
        selected_badges = sync_and_get_user_badges(user_id) if selected_player["id"] == user_id else (selected_player.get("unlocked_badges") or [])

        st.progress(len(selected_badges) / len(MASTER_BADGES), text=f"**Cabinet Completion:** `{int((len(selected_badges) / len(MASTER_BADGES)) * 100)}%` Unlocked")
        t_col1, t_col2 = st.columns(2)
        for idx, (b_name, b_desc) in enumerate(MASTER_BADGES.items()):
            is_unlocked = b_name in selected_badges
            with (t_col1 if idx % 2 == 0 else t_col2):
                if is_unlocked: st.markdown(f'<div class="trophy-card-unlocked"><b>{b_name}</b> <span style="color:#fbbf24;">(UNLOCKED)</span><br><small>{b_desc}</small></div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="trophy-card-locked"><b>🔒 {b_name}</b><br><small>{b_desc}</small></div>', unsafe_allow_html=True)

    # ------------------------------------------
    # TAB 2: RULES & INFO
    # ------------------------------------------
    with tab_rules:
        st.markdown("## 📖 Rules & Information Hub")
        st.markdown(f'''
            <div class="rule-card"><div class="rule-step-num">01 / THE CORE PREMISE</div><p>Each week brings 10 custom NFL scenarios. Every player starts with 10 tokens. Cumulative across the season.</p></div>
            <div class="rule-card"><div class="rule-step-num">02 / TOUCHDOWN SCORER BONUS</div><p>Name 1 player to score a touchdown to pocket <b style="color: {user_team_color};">+5 bonus tokens</b>.</p></div>
            <div class="rule-card"><div class="rule-step-num">03 / SCHEDULE & CUTOFFS</div><p>Submissions automatically lock down precisely <b style="color: #38bdf8;">15 minutes before the first Sunday kickoff</b>.</p></div>
        ''', unsafe_allow_html=True)

    # ------------------------------------------
    # TAB 3: PLACE BETS
    # ------------------------------------------
    with tab_bet:
        st.header("Weekly Predictions & Wagers")
        st.link_button("🏈 View NFL Scores, Lines & Fixtures ↗️", "https://www.espn.com/nfl/schedule")
        
        if not available_weeks: st.info("No active questions available yet.")
        else:
            active_unscored_weeks = [w for w in available_weeks if not (supabase.table("weekly_questions").select("winning_answer").eq("week_number", w).eq("question_number", 96).execute().data or [{}])[0].get("winning_answer") == "CLOSED"]
            if not active_unscored_weeks: st.info("🎉 All currently available weeks have been graded!")
            else:
                selected_week = st.selectbox("Select Week:", active_unscored_weeks, index=len(active_unscored_weeks) - 1)
                questions = get_cached_weekly_questions(selected_week)
                is_locked = any(q.get("winning_answer") == "LOCKED" for q in questions)

                if not questions: st.info("No questions found for this week.")
                else:
                    true_global_tokens_bet = get_true_global_token_balance(user_id)
                    all_week_bets = supabase.table("user_bets").select("question_id, pick, wager_amount").eq("user_id", user_id).eq("week_number", selected_week).execute().data
                    existing_bets_map = {b["question_id"]: b for b in all_week_bets}
                    existing_td = supabase.table("touchdown_picks").select("player_name").eq("user_id", user_id).eq("week_number", selected_week).execute().data

                    with st.form("weekly_bet_form"):
                        wagers, picks = {}, {}
                        for q in [q for q in questions if not q.get("winning_answer", "").startswith("LOCKTIME:")]:
                            q_text = q["question_text"].split(" | MATCHUP: ")[0]
                            prev_bet = existing_bets_map.get(q["id"], {})
                            with st.expander(f"Q{q['question_number']}: {q_text[:45]}...", expanded=True):
                                c1, c2 = st.columns([1, 1])
                                with c1: picks[q["id"]] = st.radio(f"Pick Q{q['question_number']}", ["Yes", "No"], index=0 if prev_bet.get("pick", "Yes") == "Yes" else 1, key=f"pick_w{selected_week}_{q['id']}_{st.session_state.form_refresh}", horizontal=True, disabled=is_locked)
                                with c2: wagers[q["id"]] = st.number_input(f"Wager Q{q['question_number']}", min_value=0, max_value=true_global_tokens_bet, value=prev_bet.get("wager_amount", 0), key=f"wager_w{selected_week}_{q['id']}_{st.session_state.form_refresh}", disabled=is_locked)

                        td_pick = st.text_input("Player Name (Touchdown Scorer)", value=existing_td[0]["player_name"] if existing_td else "", key=f"td_scorer_w{selected_week}_{st.session_state.form_refresh}", disabled=is_locked)
                        total_wagered = sum(wagers.values())

                        if total_wagered > true_global_tokens_bet: st.error(f"⚠️ Over-wagered! Allocated {total_wagered} tokens.")
                        
                        c_sub1, c_sub2 = st.columns([2, 1])
                        with c_sub1: submit_bet = st.form_submit_button("Submit Weekly Bets 🚀", type="primary", disabled=is_locked)
                        with c_sub2: clear_bet = st.form_submit_button("Clear Bet Choices 🗑️", disabled=is_locked)

                        if clear_bet and not is_locked:
                            supabase.table("user_bets").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                            supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                            st.session_state.form_refresh += 1
                            st.success("Cleared!")
                            st.rerun()

                        if submit_bet and not is_locked:
                            if contains_profanity(td_pick): st.error("⚠️ Restricted language in TD pick.")
                            elif total_wagered > true_global_tokens_bet: st.error("Cannot over-wager available tokens.")
                            else:
                                for q_id, pick_val in picks.items():
                                    supabase.table("user_bets").delete().eq("user_id", user_id).eq("question_id", q_id).execute()
                                    supabase.table("user_bets").insert({"user_id": user_id, "user_name": profile["full_name"], "week_number": selected_week, "question_id": q_id, "pick": pick_val, "wager_amount": wagers[q_id]}).execute()
                                if td_pick:
                                    supabase.table("touchdown_picks").delete().eq("user_id", user_id).eq("week_number", selected_week).execute()
                                    supabase.table("touchdown_picks").insert({"user_id": user_id, "week_number": selected_week, "player_name": td_pick, "is_correct": None}).execute()
                                st.balloons()
                                st.success("Bets successfully locked in!")

    # ------------------------------------------
    # TAB 4: MY HISTORY & SIDE-BY-SIDE COMPARISON
    # ------------------------------------------
    with tab_history:
        st.header("📜 Your Past Bets & Results")
        history_bets = supabase.table("user_bets").select("*, weekly_questions(week_number, question_number, question_text, winning_answer)").eq("user_id", user_id).execute().data
        if history_bets:
            selected_history_week = st.selectbox("Filter History by Week", sorted(list(set([b["week_number"] for b in history_bets]))), index=len(set([b["week_number"] for b in history_bets])) - 1, key="history_week_dropdown_filter")
            filtered_history_bets = [b for b in history_bets if b["week_number"] == selected_history_week]
            formatted_data = []
            for b in filtered_history_bets:
                q_info = b.get("weekly_questions", {})
                w_ans = q_info.get("winning_answer", "Pending")
                outcome = "⏳ Pending" if w_ans in ["Pending", "LOCKED"] or w_ans.startswith("LOCKTIME:") else (f"✅ Won (+{b['wager_amount']} 🪙)" if b["pick"] == w_ans else f"❌ Lost (-{b['wager_amount']} 🪙)")
                formatted_data.append({"Q#": f"Q{q_info.get('question_number', '?')}", "Question": q_info.get('question_text', 'N/A').split(" | MATCHUP: ")[0], "Your Pick": b["pick"], "Wager": f"{b['wager_amount']} 🪙", "Outcome": outcome})
            st.dataframe(pd.DataFrame(formatted_data), use_container_width=True, hide_index=True)
        else: st.info("You haven't placed any question bets yet.")

    # ------------------------------------------
    # TAB 5: LEAGUES
    # ------------------------------------------
    with tab_leagues:
        st.header("🏆 League Standings & Mini-Leagues")
        my_memberships = supabase.table("league_members").select("league_id, leagues(id, league_name, invite_code, created_by)").eq("user_id", user_id).execute().data
        all_my_leagues = [m for m in my_memberships if m.get("leagues")]
        league_filter_options = {("🏆 Global Leaderboard" if m["leagues"]["id"] == "00000000-0000-0000-0000-000000000001" else f"🛡️ {m['leagues']['league_name']} (Mini-League)"): m["leagues"]["id"] for m in all_my_leagues}

        if league_filter_options:
            selected_league_filter_label = st.selectbox("Select Standings View", list(league_filter_options.keys()), key="unified_league_view_selector")
            selected_league_filter_id = league_filter_options[selected_league_filter_label]
            is_global_view = (selected_league_filter_id == "00000000-0000-0000-0000-000000000001")
            
            allowed_peer_ids = None if is_global_view else {cm["user_id"] for cm in supabase.table("league_members").select("user_id").eq("league_id", selected_league_filter_id).execute().data or []}
            for idx, p in enumerate(get_cached_leaderboard_stats(allowed_peer_ids=allowed_peer_ids)):
                st.markdown(f'''<div class="leaderboard-row"><div><b>#{idx+1} {p['full_name']}</b> <span style="font-size: 9px; color: #38bdf8;">[{get_earned_title(p['id'])}]</span><div class="stat-pill-container"><span class="stat-pill">🪙 <b>{p['tokens']}</b></span><span class="stat-pill">🎯 {p['win_rate']}%</span><span class="stat-pill">🏈 {p['correct_tds']} TDs</span></div></div><span style="font-family: 'Bebas Neue'; font-size: 20px; color: #38bdf8;">{p['tokens']} 🪙</span></div>''', unsafe_allow_html=True)

        st.divider()
        col_create, col_join = st.columns(2)
        with col_create:
            with st.form("create_league_form"):
                new_league_name = st.text_input("League Name", placeholder="Office Chumps")
                if st.form_submit_button("Create League 🚀", type="primary"):
                    if not new_league_name.strip(): st.error("Enter a valid name.")
                    elif contains_profanity(new_league_name): st.error("Restricted language.")
                    else:
                        invite_code = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
                        res_l = supabase.table("leagues").insert({"league_name": new_league_name.strip(), "invite_code": invite_code, "created_by": user_id, "league_password": ""}).execute()
                        if res_l.data:
                            supabase.table("league_members").insert({"league_id": res_l.data[0]["id"], "user_id": user_id}).execute()
                            st.success(f"League created! Code: **{invite_code}**")
                            st.rerun()

        with col_join:
            with st.form("join_league_form"):
                code_input = st.text_input("Enter 6-Character Invite Code")
                if st.form_submit_button("Join League 🤝", type="primary"):
                    found_league = supabase.table("leagues").select("id, league_name").eq("invite_code", code_input.strip().upper()).execute().data
                    if not found_league: st.error("Invalid invite code.")
                    else:
                        target_id = found_league[0]["id"]
                        if supabase.table("league_members").select("id").eq("league_id", target_id).eq("user_id", user_id).execute().data: st.warning("Already a member!")
                        else:
                            supabase.table("league_members").insert({"league_id": target_id, "user_id": user_id}).execute()
                            st.success("Successfully joined!")
                            st.rerun()

    # ------------------------------------------
    # TAB 6: SETTINGS
    # ------------------------------------------
    with tab_settings:
        st.header("⚙️ Account & App Settings")
        with st.form("settings_password_form"):
            new_pass1, new_pass2 = st.text_input("New Password", type="password"), st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Update Password 🔑"):
                if len(new_pass1) < 6: st.warning("Password must be at least 6 characters.")
                elif new_pass1 != new_pass2: st.error("Passwords do not match.")
                else: supabase.auth.update_user({"password": new_pass1}); st.success("Password updated!")

    # ------------------------------------------
    # TAB: LEAGUE ADMIN
    # ------------------------------------------
    if is_any_league_admin:
        with tab_league_admin:
            st.markdown("## ⭐ League Commissioner Administration")
            admin_leagues_list = supabase.table("leagues").select("id, league_name, invite_code, league_password, created_by").neq("id", "00000000-0000-0000-0000-000000000001").execute().data if profile.get("is_admin") else my_administered_leagues
            if admin_leagues_list:
                selected_league = {l["league_name"]: l for l in admin_leagues_list}[st.selectbox("Select Mini-League to Administer", list({l["league_name"]: l for l in admin_leagues_list}.keys()))]
                st.metric("Invite Code", selected_league["invite_code"])

    # ------------------------------------------
    # TAB: SYSTEM ADMIN CONTROL
    # ------------------------------------------
    if profile.get("is_admin"):
        with tab_admin:
            st.header("⚙️ System Admin Management Portal")
            admin_sec = st.radio("Select Action", ["Manage Questions", "Grade Week & Calculate Points", "App Access Control"], horizontal=True)
            if admin_sec == "Manage Questions":
                st.subheader("Manage Weekly Questions")
                selected_manage_week = st.number_input("Week Number", min_value=1, value=1)
                with st.form("admin_questions_form"):
                    prompts = [st.text_input(f"Question {i} Prompt", key=f"adm_q_{i}") for i in range(1, 11)]
                    if st.form_submit_button("Save Questions", type="primary"):
                        for i, p in enumerate(prompts, 1):
                            if p.strip():
                                supabase.table("weekly_questions").insert({"week_number": selected_manage_week, "question_number": i, "question_text": p.strip(), "winning_answer": "Pending"}).execute()
                        st.success("Questions saved!")
            elif admin_sec == "App Access Control":
                if st.button("Save Access Control Settings 🛡️", type="primary"):
                    st.success("Access settings updated!")
