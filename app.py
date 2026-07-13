import io
import os
import asyncio
import httpx
import base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

# ================= ADJUSTMENT SETTINGS =================
TARGET_WIDTH = 2048
TARGET_HEIGHT = 512
AVATAR_SIZE = 512
BANNER_WIDTH = TARGET_WIDTH - AVATAR_SIZE # 1536

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
BASE64_URL = "aHR0cHM6Ly9jZG4uanNkZWxpdnIubmV0L2doL1NoYWhHQ3JlYXRvci9pY29uQG1haW4vUE5H"
IMAGE_BASE_URL = base64.b64decode(BASE64_URL).decode('utf-8')
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
    except Exception as e:
        print(f"[FONT ERROR] Could not load custom font {font_file}: {e}")
    return ImageFont.load_default()

# Avatar Fetcher
async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) in ["0", "None", "null"]:
        return None
    url = f"{IMAGE_BASE_URL}/{item_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching image {item_id}: {e}")
    return None

# Banner Fetcher
async def fetch_banner_bytes(banner_id):
    if not banner_id or str(banner_id) in ["0", "None", "null"]:
        return None
    url = f"https://kdhdsdf.vercel.app/banner/{banner_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching banner {banner_id}: {e}")
    return None

def bytes_to_image(img_bytes, default_w=512, default_h=512):
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except:
            pass
    return Image.new("RGBA", (default_w, default_h), (255, 255, 255, 0))

# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes):
    # Load raw images
    avatar_img = bytes_to_image(avatar_bytes, default_w=AVATAR_SIZE, default_h=AVATAR_SIZE)
    banner_img = bytes_to_image(banner_bytes, default_w=BANNER_WIDTH, default_h=TARGET_HEIGHT)
    
    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    # 1. Process Avatar (Zoom to fill 512x512 area after cropping alpha)
    bbox = avatar_img.getbbox()
    if bbox:
        avatar_img = avatar_img.crop(bbox)
    
    av_w, av_h = avatar_img.size
    # Calculate scale to FILL the 512x512 area (Zoom effect)
    scale = max(AVATAR_SIZE / av_w, AVATAR_SIZE / av_h)
    new_av_size = (int(av_w * scale), int(av_h * scale))
    avatar_img = avatar_img.resize(new_av_size, Image.LANCZOS)
    
    # Center Crop the zoomed avatar to exactly 512x512
    left_av = (new_av_size[0] - AVATAR_SIZE) // 2
    top_av = (new_av_size[1] - AVATAR_SIZE) // 2
    avatar_final = avatar_img.crop((left_av, top_av, left_av + AVATAR_SIZE, top_av + AVATAR_SIZE))

    # 2. Process Banner (Resize and Center Crop to fill 1536x512)
    b_w, b_h = banner_img.size
    scale_b = max(BANNER_WIDTH / b_w, TARGET_HEIGHT / b_h)
    new_b_size = (int(b_w * scale_b), int(b_h * scale_b))
    banner_img = banner_img.resize(new_b_size, Image.LANCZOS)
    
    left_b = (new_b_size[0] - BANNER_WIDTH) // 2
    top_b = (new_b_size[1] - TARGET_HEIGHT) // 2
    banner_final = banner_img.crop((left_b, top_b, left_b + BANNER_WIDTH, top_b + TARGET_HEIGHT))

    # 3. Create Canvas and Composite (Blueprint Layout)
    combined = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (255, 255, 255, 255))
    
    # Place Avatar on the left (0 to 512)
    combined.paste(avatar_final, (0, 0), avatar_final)
    # Place Banner on the right (512 to 2048)
    combined.paste(banner_final, (AVATAR_SIZE, 0))

    draw = ImageDraw.Draw(combined)
    
    font_large = load_unicode_font(140)
    font_large_cherokee = load_unicode_font(140, FONT_CHEROKEE)
    font_small = load_unicode_font(100)
    font_small_cherokee = load_unicode_font(100, FONT_CHEROKEE)
    font_level = load_unicode_font(70)

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

    # Place text on the banner area (starting at X=512 + margin)
    text_margin = 80
    draw_text(AVATAR_SIZE + text_margin, 50, name, font_large, font_large_cherokee, 5)
    if guild:
        draw_text(AVATAR_SIZE + text_margin, 260, guild, font_small, font_small_cherokee, 4)

    # Level Display (Red Box at bottom right as per blueprint)
    lvl_text = f"Lvl. {level}"
    bbox_lvl = draw.textbbox((0, 0), lvl_text, font=font_level)
    lw, lh = bbox_lvl[2] - bbox_lvl[0], bbox_lvl[3] - bbox_lvl[1]
    
    # Box position (bottom right)
    box_padding_x = 30
    box_padding_y = 20
    rect_coords = [TARGET_WIDTH - lw - 80, TARGET_HEIGHT - lh - 60, TARGET_WIDTH - 30, TARGET_HEIGHT - 20]
    draw.rectangle(rect_coords, fill=(255, 59, 59, 255)) # Red Box
    draw.text((TARGET_WIDTH - lw - 55, TARGET_HEIGHT - lh - 50), lvl_text, font=font_level, fill="white")
    
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

    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    account_name = basic_info.get("nickname", "Unknown")
    account_level = basic_info.get("level", "0")
    guild_name = clan_info.get("clanName", "")

    avatar_task = fetch_image_bytes(avatar_id)
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
