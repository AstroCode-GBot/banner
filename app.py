import io
import os
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

# ================= ADJUSTMENT SETTINGS =================
# আপনার পাঠানো উদাহরণের ব্যানারের ডিজাইন অনুযায়ী এই পজিশনগুলো (X, Y) সামান্য পরিবর্তন করে নিতে পারেন
AVATAR_POS_X = 50       # ব্যানারের যেখানে অ্যাভাটার বসবে তার X অক্ষ
AVATAR_POS_Y = 50       # ব্যানারের যেখানে অ্যাভাটার বসবে তার Y অক্ষ
AVATAR_SIZE = 150       # অ্যাভাটারটির সাইজ (বক্সের সাইজ অনুযায়ী রিলিজ বা বড় করতে পারেন)

LEVEL_POS_X = 850       # ব্যানারের লেভেল টেক্সট বসানোর X অক্ষ
LEVEL_POS_Y = 320       # ব্যানারের লেভেল টেক্সট বসানোর Y অক্ষ

# ================= Lifespan =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INFO_API_URL = "https://atozinfo.vercel.app/info?uid="

# অ্যাভাটার ইমেজ ডাউনলোডের বেস ইউআরএল (আগেরটাই রাখা হলো)
AVATAR_BASE_URL = "https://cdn.jsdelivr.net/gh/ShahGCreator/icon@main/PNG"

# আপনার দেওয়া GitHub রিপোজিটরির র (Raw) কন্টেন্ট ইউআরএল যেখান থেকে ব্যানার ডিরেক্ট ডাউনলোড হবে
BANNER_BASE_URL = "https://raw.githubusercontent.com/AstroCode-GBot/kdhdsdf/main/banner"

FONT_FILE = "arial_unicode_bold.otf"
FONT_CHEROKEE = "NotoSansCherokee.ttf"

client = httpx.AsyncClient(
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    },
    timeout=20.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

def load_unicode_font(size, font_file=FONT_FILE):
    try:
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except:
        pass
    return ImageFont.load_default()

async def fetch_avatar_bytes(avatar_id):
    if not avatar_id or str(avatar_id) in ["0", "None", "null"]:
        return None
    url = f"{AVATAR_BASE_URL}/{avatar_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching avatar {avatar_id}: {e}")
    return None

async def fetch_banner_bytes(banner_id):
    if not banner_id or str(banner_id) in ["0", "None", "null"]:
        return None
    # GitHub থেকে সরাসরি png ফরম্যাটে ব্যানারটি নিয়ে আসবে
    url = f"{BANNER_BASE_URL}/{banner_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching banner {banner_id}: {e}")
    return None

def bytes_to_image(img_bytes, default_size=(400, 400)):
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except:
            pass
    return Image.new("RGBA", default_size, (200, 200, 200, 255))
    
# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes):
    # ব্যানারটিকে ব্যাকগ্রাউন্ড হিসেবে ওপেন করা হচ্ছে
    banner_img = bytes_to_image(banner_bytes, default_size=(1024, 400))
    avatar_img = bytes_to_image(avatar_bytes, default_size=(200, 200))

    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    # নতুন নিয়মে ব্যানারটাই হবে মেইন ক্যানভাস/ব্যাকগ্রাউন্ড
    combined = banner_img.copy()
    
    # অ্যাভাটার রিসাইজ এবং ব্যানারের নির্ধারিত স্থানে পেস্ট (ওভারল্যাপ করা)
    avatar_img = avatar_img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    combined.paste(avatar_img, (AVATAR_POS_X, AVATAR_POS_Y), avatar_img)

    draw = ImageDraw.Draw(combined)
    
    # ফন্ট সাইজগুলো ব্যানারের রেজোলিউশন অনুযায়ী অ্যাডজাস্ট করতে পারেন
    font_large = load_unicode_font(50)
    font_large_cherokee = load_unicode_font(50, FONT_CHEROKEE)
    font_small = load_unicode_font(35)
    font_small_cherokee = load_unicode_font(35, FONT_CHEROKEE)
    font_level = load_unicode_font(30)

    def is_cherokee(c):
        return 0x13A0 <= ord(c) <= 0x13FF or 0xAB70 <= ord(c) <= 0xABBF

    def draw_text(x, y, text, f_main, f_alt, stroke):
        cx = x
        for ch in text:
            f = f_alt if is_cherokee(ch) else f_main
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    draw.text((cx + dx, y + dy), ch, font=f, fill="black")
            draw.text((cx, y), ch, font=f, fill="white")
            cx += f.getlength(ch)

    # নাম এবং গিল্ড এর টেক্সট লজিক (নামের পজিশন অ্যাভাটার এর ডান পাশে রাখার জন্য)
    text_start_x = AVATAR_POS_X + AVATAR_SIZE + 30
    draw_text(text_start_x, AVATAR_POS_Y + 10, name, font_large, font_large_cherokee, 3)
    if guild:
        draw_text(text_start_x, AVATAR_POS_Y + 75, guild, font_small, font_small_cherokee, 2)

    # লেভেল ডিসপ্লে (সরাসরি ব্যানারের লেভেল আইকন/বক্সের ওপরে বসবে)
    lvl_text = f"{level}" # শুধু লেভেল নাম্বার দিতে চাইলে `level`, অথবা `Lvl.{level}` লিখতে পারেন
    draw.text((LEVEL_POS_X, LEVEL_POS_Y), lvl_text, font=font_level, fill="white", stroke_width=2, stroke_fill="black")

    img_io = io.BytesIO()
    combined.save(img_io, "PNG")
    img_io.seek(0)
    return img_io

@app.get("/astro")
async def get_banner(uid: str):
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")

    try:
        resp = await client.get(f"{INFO_API_URL}{uid}")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Player Info API is down")
        
        data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    basic_info = data.get("basicInfo", {})
    clan_info = data.get("clanBasicInfo", {})
    
    if not basic_info:
        raise HTTPException(status_code=404, detail="Player data not found in API response")

    # ডাটা এক্সট্রাকশন
    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    account_name = basic_info.get("nickname", "Unknown")
    account_level = basic_info.get("level", "0")
    guild_name = clan_info.get("clanName", "")

    print(f"DEBUG: Processing Player -> Name: {account_name}, AvatarID: {avatar_id}, BannerID: {banner_id}")

    # আলাদা আলাদা সোর্স থেকে ইমেজ নিয়ে আসা হচ্ছে
    avatar_task = fetch_avatar_bytes(avatar_id)
    banner_task = fetch_banner_bytes(banner_id)
    avatar, banner = await asyncio.gather(avatar_task, banner_task)
    
    banner_data = {
        "AccountLevel": account_level,
        "AccountName": account_name,
        "GuildName": guild_name
    }

    loop = asyncio.get_event_loop()
    img_io = await loop.run_in_executor(process_pool, process_banner_image, banner_data, avatar, banner)

    return Response(
        content=img_io.getvalue(), 
        media_type="image/png", 
        headers={"Cache-Control": "public, max-age=300"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
