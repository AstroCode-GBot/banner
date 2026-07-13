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

# ================= CONFIGURATION SECTION =================
# Adjust these values to align perfectly with your GitHub template PNGs
# All measurements are in pixels

# GitHub Repository Settings
GITHUB_BANNER_BASE = "https://raw.githubusercontent.com/AstroCode-GBot/kdhdsdf/main/banner/"
DEFAULT_BANNER_FILENAME = "901054015.png"

# Avatar Positioning (Player avatar over template placeholder)
TEMPLATE_AVATAR_X = 15
TEMPLATE_AVATAR_Y = 15
TEMPLATE_AVATAR_SIZE = 370  # Width and Height (Square)

# Level Positioning (Covering old level)
LEVEL_X = 840
LEVEL_Y = 320
LEVEL_FONT_SIZE = 55
LEVEL_TEXT_COLOR = "white"
# Set a background color if you need to "wipe" the area before drawing level
# Use None to just draw text directly
LEVEL_MASK_COLOR = None 

# Name & Guild Positioning (Relative to template)
NAME_X = 420
NAME_Y = 40
NAME_FONT_SIZE = 125

GUILD_X = 420
GUILD_Y = 220
GUILD_FONT_SIZE = 95

# Canvas Settings
TARGET_HEIGHT = 400 # Base height for scaling logic

# ================= ADJUSTMENT SETTINGS (LEGACY COMPATIBILITY) =================
AVATAR_ZOOM = 1.0  # Kept for logic, but controlled by TEMPLATE_AVATAR_SIZE now
AVATAR_SHIFT_Y = 0
AVATAR_SHIFT_X = 0

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
    except:
        pass
    return ImageFont.load_default()

async def fetch_image_bytes(item_id, is_banner=False):
    """
    Fetches image bytes. 
    If is_banner is True, it pulls from GitHub.
    If it fails, it tries to pull the default banner.
    """
    if not item_id or str(item_id) in ["0", "None", "null"]:
        if is_banner:
            item_id = DEFAULT_BANNER_FILENAME.replace(".png", "")
        else:
            return None

    if is_banner:
        url = f"{GITHUB_BANNER_BASE}{item_id}.png"
    else:
        url = f"{IMAGE_BASE_URL}/{item_id}.png"

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
        
        # Fallback for banner only
        if is_banner and resp.status_code != 200:
            print(f"DEBUG: Banner {item_id} not found, loading default.")
            fallback_resp = await client.get(f"{GITHUB_BANNER_BASE}{DEFAULT_BANNER_FILENAME}")
            return fallback_resp.content if fallback_resp.status_code == 200 else None
            
    except Exception as e:
        print(f"DEBUG: Error fetching image {item_id}: {e}")
        if is_banner: # Last resort fallback
             try:
                fallback_resp = await client.get(f"{GITHUB_BANNER_BASE}{DEFAULT_BANNER_FILENAME}")
                return fallback_resp.content
             except: return None
    return None

def bytes_to_image(img_bytes):
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except:
            pass
    # Return transparent placeholder if error
    return Image.new("RGBA", (400, 400), (0, 0, 0, 0))

# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes):
    # Load Template (from GitHub) and Player Avatar
    template_img = bytes_to_image(banner_bytes)
    avatar_img = bytes_to_image(avatar_bytes)
    
    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    # 1. AVATAR REPLACEMENT LOGIC
    # Resize player avatar to match template placeholder
    avatar_img = avatar_img.resize((TEMPLATE_AVATAR_SIZE, TEMPLATE_AVATAR_SIZE), Image.LANCZOS)
    
    # Create final canvas based on template size
    combined = template_img.copy()
    
    # Paste Avatar exactly over the template placeholder (preserving alpha)
    combined.paste(avatar_img, (TEMPLATE_AVATAR_X, TEMPLATE_AVATAR_Y), avatar_img)

    draw = ImageDraw.Draw(combined)
    
    # Load Fonts
    font_large = load_unicode_font(NAME_FONT_SIZE)
    font_large_cherokee = load_unicode_font(NAME_FONT_SIZE, FONT_CHEROKEE)
    font_small = load_unicode_font(GUILD_FONT_SIZE)
    font_small_cherokee = load_unicode_font(GUILD_FONT_SIZE, FONT_CHEROKEE)
    font_level = load_unicode_font(LEVEL_FONT_SIZE)

    # 2. TEXT RENDERING ENGINE (UNTOUCHED)
    def is_cherokee(c):
        return 0x13A0 <= ord(c) <= 0x13FF or 0xAB70 <= ord(c) <= 0xABBF

    def draw_text(x, y, text, f_main, f_alt, stroke):
        cx = x
        for ch in text:
            f = f_alt if is_cherokee(ch) else f_main
            # Stroke logic
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    if dx == 0 and dy == 0: continue
                    draw.text((cx + dx, y + dy), ch, font=f, fill="black")
            # Main text
            draw.text((cx, y), ch, font=f, fill="white")
            cx += f.getlength(ch)

    # Draw Name and Guild using original offsets from configuration
    draw_text(NAME_X, NAME_Y, name, font_large, font_large_cherokee, 4)
    
    if guild:
        draw_text(GUILD_X, GUILD_Y, guild, font_small, font_small_cherokee, 3)

    # 3. LEVEL REPLACEMENT LOGIC
    lvl_text = f"Lvl.{level}"
    
    # If a mask color is provided, draw a rectangle to hide old level text
    if LEVEL_MASK_COLOR:
        bbox = draw.textbbox((LEVEL_X, LEVEL_Y), lvl_text, font=font_level)
        draw.rectangle(bbox, fill=LEVEL_MASK_COLOR)
    
    # Draw new level exactly on top
    # Using a small black stroke for level to ensure readability/coverage
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            draw.text((LEVEL_X + dx, LEVEL_Y + dy), lvl_text, font=font_level, fill="black")
    
    draw.text((LEVEL_X, LEVEL_Y), lvl_text, font=font_level, fill=LEVEL_TEXT_COLOR)

    # Save to IO
    img_io = io.BytesIO()
    combined.save(img_io, "PNG", optimize=True)
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

    # ================= MAPPING API RESPONSE =================
    basic_info = data.get("basicInfo", {})
    clan_info = data.get("clanBasicInfo", {})
    
    if not basic_info:
        raise HTTPException(status_code=404, detail="Player data not found in API response")

    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    account_name = basic_info.get("nickname", "Unknown")
    account_level = basic_info.get("level", "0")
    guild_name = clan_info.get("clanName", "")

    # Fetching Assets
    avatar_task = fetch_image_bytes(avatar_id, is_banner=False)
    banner_task = fetch_image_bytes(banner_id, is_banner=True) # Now pulls from GitHub
    
    avatar_bytes, banner_bytes = await asyncio.gather(avatar_task, banner_task)

    banner_data = {
        "AccountLevel": account_level,
        "AccountName": account_name,
        "GuildName": guild_name
    }

    loop = asyncio.get_event_loop()
    img_io = await loop.run_in_executor(
        process_pool, 
        process_banner_image, 
        banner_data, 
        avatar_bytes, 
        banner_bytes
    )

    return Response(
        content=img_io.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
