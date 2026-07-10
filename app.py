import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

INFO_API_URL = "https://info.killersharmabot.online/player-info"
IMAGE_GEN_URL = "https://image.killersharmabot.online/banner-image"

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timeout ৫ সেকেন্ড রাখা হয়েছে যাতে রিকোয়েস্ট ঝুলে না থাকে
client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=5.0,
    follow_redirects=True
)

@app.get("/")
async def home():
    return {"status": "Vercel Optimized Banner API Running", "endpoint": "/astro?uid=UID"}

@app.get("/astro")
async def get_banner(uid: str):
    # ১. প্লেয়ার ইনফো API থেকে ডেটা আনা
    url = f"{INFO_API_URL}?uid={uid}"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(502, f"Info API returned {resp.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Failed to fetch player info: {str(e)}")

    data = resp.json()
    basic_info = data.get("basicInfo") or {}
    profile_info = data.get("profileInfo") or {}
    clan_info = data.get("clanBasicInfo") or {}

    name = basic_info.get("nickname")
    if not name:
        raise HTTPException(404, "Account not found or invalid response from info API")

    # ২. নতুন API এর কুয়েরি প্যারামিটার তৈরি
    params = {
        "headPic": basic_info.get("headPic", ""),
        "bannerId": basic_info.get("bannerId", ""),
        "name": name,
        "level": basic_info.get("level", 2),
        "guild": clan_info.get("clanName", ""),
        "pinId": basic_info.get("pinId", "900000012"),
        "celebrity": basic_info.get("celebrityStatus", 0),
        "primeLevel": basic_info.get("primeLevel", 0) or profile_info.get("primeLevel", 0),
        "frame": basic_info.get("frame", "") or profile_info.get("frame", "")
    }

    # ৩. ইমেজ জেনারেটর API থেকে ইমেজ ফেচ করা
    try:
        img_resp = await client.get(IMAGE_GEN_URL, params=params)
        if img_resp.status_code != 200:
            raise HTTPException(502, f"Image Generator API returned {img_resp.status_code}")
    except Exception as e:
        raise HTTPException(502, f"Failed to generate banner image: {str(e)}")

    # ৪. Vercel CDN ক্যাশিং হেডার সেট করা (৫ মিনিটের জন্য ক্যাশ থাকবে)
    headers = {
        "Cache-Control": "public, max-age=300, s-maxage=300, stale-while-revalidate=60"
    }

    # ৫. ইমেজ রেসপন্স পাঠানো
    return Response(content=img_resp.content, media_type="image/png", headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
