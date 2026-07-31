from supabase import create_client

SUPABASE_URL="https://avgyzouzwfxzztjsaqal.supabase.co/rest/v1/"

SUPABASE_KEY="sb_publishable_G871y1zAiBpstlKOhDp4lQ_Nq8B6LMQ"

supabase=create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)