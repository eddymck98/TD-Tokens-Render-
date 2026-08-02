@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email")
    password = request.form.get("password")
    try:
        # Authenticate via Supabase Auth
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        session["user"] = res.user.email
        session["user_id"] = res.user.id
        return redirect(url_for("index"))
    except Exception as e:
        return f"Login failed: {e}", 400

@app.route("/signup", methods=["POST"])
def signup():
    email = request.form.get("email")
    password = request.form.get("password")
    full_name = request.form.get("full_name")
    
    try:
        # Register user with Supabase Auth
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            # Automatically provision their initial user profile and starting tokens
            supabase.table("profiles").insert({
                "id": res.user.id,
                "email": email,
                "full_name": full_name,
                "tokens": 10, # New players start with 10 free tokens
                "is_admin": False,
                "favorite_team": "🏈 Free Agent / Neutral",
                "bio": "Ready for Kickoff!",
                "avatar_emoji": "🏈",
                "featured_badges": [],
                "unlocked_badges": [],
                "avatar_border": "solid",
                "favorite_player": "",
                "avatar_color": "#1e3a8a",
                "selected_title": "🏈 Gridiron Contender"
            }).execute()
        return redirect(url_for("index"))
    except Exception as e:
        return f"Sign up failed: {e}", 400
