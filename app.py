import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from aiocache import cached  # ক্যাশিং এর জন্য লাইব্রেরি

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

# Timeout কমিয়ে দেওয়া হয়েছে যাতে কোনো সার্ভার ডাউন থাকলে আপনার API ঝুলে না থাকে
client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=5.0, 
    follow_redirects=True
)

# এই ফাংশনটি প্রতিটা UID এর ইমেজ ৫ মিনিটের জন্য মেমোরিতে সেভ রাখবে
@cached(ttl=300)  # ttl=300 মানে ৩০০ সেকেন্ড বা ৫ মিনিট ক্যাশ থাকবে
async def fetch_and_generate_banner(uid: str) -> bytes:
    # ১. প্লেয়ার ইনফো ফেচ করা
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

    # ২. প্যারামিটার তৈরি করা
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

    # ৩. ইমেজ জেনারেট করা
    try:
        img_resp = await client.get(IMAGE_GEN_URL, params=params)
        if img_resp.status_code != 200:
            raise HTTPException(502, f"Image Generator API returned {img_resp.status_code}")
        return img_resp.content  # ইমেজের বাইনারি ডেটা রিটার্ন
    except Exception as e:
        raise HTTPException(502, f"Failed to generate banner image: {str(e)}")


@app.get("/")
async def home():
    return {"status": "Cached Banner API Running", "endpoint": "/astro?uid=UID"}


@app.get("/astro")
async def get_banner(uid: str):
    # ক্যাশ ফাংশন কল করা হচ্ছে
    img_content = await fetch_and_generate_banner(uid)
    return Response(content=img_content, media_type="image/png")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)