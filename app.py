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

# GitHub Repository Settings
GITHUB_BANNER_BASE = "https://raw.githubusercontent.com/AstroCode-GBot/kdhdsdf/main/banner/"
DEFAULT_BANNER_FILENAME = "901054015.png"

# Avatar Positioning (Player avatar over template placeholder)
TEMPLATE_AVATAR_X = 15
TEMPLATE_AVATAR_Y = 15
TEMPLATE_AVATAR_SIZE = 370  # Width/Height of the avatar on the template

# Name Positioning
NAME_X = 420
NAME_Y = 140 # Adjusted for "Only Name" layout
NAME_FONT_SIZE = 125
NAME_STROKE_WIDTH = 4

# Level Masking (To hide the "Lvl. 1" baked into the GitHub template)
# This draws a box over the template's level area to make it invisible
HIDE_TEMPLATE_LEVEL = True
LEVEL_MASK_X1, LEVEL_MASK_Y1 = 800, 300 
LEVEL_MASK_X2, LEVEL_MASK_Y2 = 1000, 400
LEVEL_MASK_COLOR = (0, 0, 0, 255) # Usually black to match banner bottom

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
    if not item_id or str(item_id) in ["0", "None", "null"]:
        if is_banner: item_id = "default"
        else: return None

    url = f"{GITHUB_BANNER_BASE}{item_id}.png" if is_banner else f"{IMAGE_BASE_URL}/{item_id}.png"

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
        if is_banner: # Fallback to default.png from GitHub
            fallback = await client.get(f"{GITHUB_BANNER_BASE}{DEFAULT_BANNER_FILENAME}")
            return fallback.content if fallback.status_code == 200 else None
    except:
        return None

def bytes_to_image(img_bytes):
    if img_bytes:
        try:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except: pass
    return Image.new("RGBA", (400, 400), (0, 0, 0, 0))

# ================= IMAGE PROCESS =================
def process_banner_image(data, avatar_bytes, banner_bytes):
    # Load Template and Player Avatar
    template_img = bytes_to_image(banner_bytes)
    avatar_img = bytes_to_image(avatar_bytes)
    name = data.get("AccountName", "Unknown")

    # Create canvas from template
    combined = template_img.copy()
    draw = ImageDraw.Draw(combined)

    # 1. HIDE OLD LEVEL (Masking)
    if HIDE_TEMPLATE_LEVEL:
        draw.rectangle([LEVEL_MASK_X1, LEVEL_MASK_Y1, LEVEL_MASK_X2, LEVEL_MASK_Y2], fill=LEVEL_MASK_COLOR)

    # 2. AVATAR REPLACEMENT
    avatar_img = avatar_img.resize((TEMPLATE_AVATAR_SIZE, TEMPLATE_AVATAR_SIZE), Image.LANCZOS)
    combined.paste(avatar_img, (TEMPLATE_AVATAR_X, TEMPLATE_AVATAR_Y), avatar_img)

    # 3. TEXT ENGINE (NAME ONLY)
    font_large = load_unicode_font(NAME_FONT_SIZE)
    font_large_cherokee = load_unicode_font(NAME_FONT_SIZE, FONT_CHEROKEE)

    def is_cherokee(c):
        return 0x13A0 <= ord(c) <= 0x13FF or 0xAB70 <= ord(c) <= 0xABBF

    def draw_text(x, y, text, f_main, f_alt, stroke):
        cx = x
        for ch in text:
            f = f_alt if is_cherokee(ch) else f_main
            # Draw Stroke
            for dx in range(-stroke, stroke + 1):
                for dy in range(-stroke, stroke + 1):
                    if dx == 0 and dy == 0: continue
                    draw.text((cx + dx, y + dy), ch, font=f, fill="black")
            # Draw Main White Text
            draw.text((cx, y), ch, font=f, fill="white")
            cx += f.getlength(ch)

    # Draw the Player Name
    draw_text(NAME_X, NAME_Y, name, font_large, font_large_cherokee, NAME_STROKE_WIDTH)

    # Note: Guild and Level drawing omitted as per "only avatar and banner name" request.

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
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    basic_info = data.get("basicInfo", {})
    if not basic_info:
        raise HTTPException(status_code=404, detail="Player not found")

    avatar_id = basic_info.get("headPic")
    banner_id = basic_info.get("bannerId")
    account_name = basic_info.get("nickname", "Unknown")

    avatar_task = fetch_image_bytes(avatar_id, is_banner=False)
    banner_task = fetch_image_bytes(banner_id, is_banner=True)
    
    avatar_bytes, banner_bytes = await asyncio.gather(avatar_task, banner_task)

    banner_data = {"AccountName": account_name}

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
