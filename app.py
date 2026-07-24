import io
import os
import asyncio
import httpx
import base64
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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
# Avatar API: https://iconapi.wasmer.app/{id}
IMAGE_BASE_URL = "https://iconapi.wasmer.app"
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

async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) in ["0", "None", "null"]:
        return None
    url = f"{IMAGE_BASE_URL}/{item_id}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching image {item_id}: {e}")
    return None

async def fetch_banner_bytes(banner_id):
    default_path = os.path.join(os.path.dirname(__file__), "default.png")
    if not banner_id or str(banner_id) in ["0", "None", "null"]:
        if os.path.exists(default_path):
            with open(default_path, "rb") as f:
                return f.read()
        return None
        
    url = f"https://kdhdsdf.vercel.app/banner/{banner_id}.png"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"DEBUG: Error fetching banner {banner_id}: {e}")
    
    if os.path.exists(default_path):
        with open(default_path, "rb") as f:
            return f.read()
    return None

def bytes_to_image(img_bytes, default_w=512, default_h=512, color=(0, 0, 0, 0)):
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except:
            pass
    return Image.new("RGBA", (default_w, default_h), color)

# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes):
    # Load images
    avatar_raw = bytes_to_image(avatar_bytes, AVATAR_SIZE, AVATAR_SIZE)
    banner_raw = bytes_to_image(banner_bytes, BANNER_WIDTH, TARGET_HEIGHT, color=(30, 30, 30, 255))
    
    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    # 1. Avatar: Crop to visible and Zoom
    bbox = avatar_raw.getbbox()
    if bbox:
        avatar_raw = avatar_raw.crop(bbox)
    
    orig_av_w, orig_av_h = avatar_raw.size
    scale_av = max(AVATAR_SIZE / orig_av_w, AVATAR_SIZE / orig_av_h)
    new_av_size = (int(orig_av_w * scale_av), int(orig_av_h * scale_av))
    avatar_resized = avatar_raw.resize(new_av_size, Image.LANCZOS)
    
    left_av = (avatar_resized.width - AVATAR_SIZE) // 2
    top_av = (avatar_resized.height - AVATAR_SIZE) // 2
    avatar_final = avatar_resized.crop((left_av, top_av, left_av + AVATAR_SIZE, top_av + AVATAR_SIZE))

    # 2. Banner: Aspect Fill 1536x512
    b_w, b_h = banner_raw.size
    scale_b = max(BANNER_WIDTH / b_w, TARGET_HEIGHT / b_h)
    new_b_size = (int(b_w * scale_b), int(b_h * scale_b))
    banner_resized = banner_raw.resize(new_b_size, Image.LANCZOS)
    
    left_b = (banner_resized.width - BANNER_WIDTH) // 2
    top_b = (banner_resized.height - TARGET_HEIGHT) // 2
    banner_final = banner_resized.crop((left_b, top_b, left_b + BANNER_WIDTH, top_b + TARGET_HEIGHT))

    # 3. Canvas Composition
    combined = Image.new("RGBA", (TARGET_WIDTH, TARGET_HEIGHT), (20, 20, 20, 255))
    combined.paste(banner_final, (AVATAR_SIZE, 0))
    combined.paste(avatar_final, (0, 0), avatar_final)

    draw = ImageDraw.Draw(combined)
    
    # Fonts
    font_large = load_unicode_font(140)
    font_large_cherokee = load_unicode_font(140, FONT_CHEROKEE)
    font_small = load_unicode_font(100)
    font_small_cherokee = load_unicode_font(100, FONT_CHEROKEE)
    font_level = load_unicode_font(115) # Increased size for better visibility

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

    # Name and Guild
    text_margin = 80
    draw_text(AVATAR_SIZE + text_margin, 50, name, font_large, font_large_cherokee, 6)
    if guild:
        draw_text(AVATAR_SIZE + text_margin, 260, guild, font_small, font_small_cherokee, 5)

    # 4. Level Section: Aesthetic Transparent Blur
    lvl_text = f"Lvl. {level}"
    bbox_lvl = draw.textbbox((0, 0), lvl_text, font=font_level)
    lw, lh = bbox_lvl[2] - bbox_lvl[0], bbox_lvl[3] - bbox_lvl[1]
    
    # Box dimensions flush to bottom-right edge
    box_w = lw + 30
    box_h = lh + 20
    rect_x1 = TARGET_WIDTH - box_w
    rect_y1 = TARGET_HEIGHT - box_h
    rect_x2 = TARGET_WIDTH
    rect_y2 = TARGET_HEIGHT

    # Blur Crop
    blur_region = combined.crop((rect_x1, rect_y1, rect_x2, rect_y2))
    blur_region = blur_region.filter(ImageFilter.GaussianBlur(radius=35))
    combined.paste(blur_region, (rect_x1, rect_y1))

    # Center level text in blurred region
    tx = rect_x1 + (box_w - lw) // 2
    ty = rect_y1 + (box_h - lh) // 2 - 15
    
    # Reduced stroke for aesthetic look
    s_val = 3 
    for dx in range(-s_val, s_val + 1):
        for dy in range(-s_val, s_val + 1):
            draw.text((tx + dx, ty + dy), lvl_text, font=font_level, fill="black")
    draw.text((tx, ty), lvl_text, font=font_level, fill="white")
    
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

#if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="127.0.0.1", port=8080)
