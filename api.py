from fastapi import FastAPI
from utils.database import get_supabase_client

app = FastAPI()
supabase = get_supabase_client()

@app.get("/api/profile/{user_id}")
def get_profile(user_id: str):
    response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    return response.data
