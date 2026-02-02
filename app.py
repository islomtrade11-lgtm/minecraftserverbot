import asyncio
import os
import time
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# ================== ENV ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_IDS_RAW = os.getenv("OWNER_IDS")
PLAY_API_KEY = os.getenv("PLAY_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")

if not all([BOT_TOKEN, OWNER_IDS_RAW, PLAY_API_KEY, SERVER_ID]):
    raise RuntimeError("Missing required environment variables")

ALLOWED_USERS = {int(x.strip()) for x in OWNER_IDS_RAW.split(",") if x.strip()}

API_BASE = "https://panel.play.hosting/api/client"

HEADERS = {
    "Authorization": f"Bearer {PLAY_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ================== BOT ==================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

last_click = {}

# ================== UI ==================

def keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="▶️ Start", callback_data="start"),
            InlineKeyboardButton(text="⏹ Stop", callback_data="stop"),
            InlineKeyboardButton(text="🔄 Restart", callback_data="restart"),
        ],
        [
            InlineKeyboardButton(text="📊 Status", callback_data="status")
        ]
    ])

def allowed(uid: int) -> bool:
    return uid in ALLOWED_USERS

# ================== API ==================

async def send_power(signal: str) -> bool:
    url = f"{API_BASE}/servers/{SERVER_ID}/power"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=HEADERS,
                json={"signal": signal},
                timeout=10
            ) as resp:
                return resp.status == 204
    except Exception:
        return False

async def get_status() -> str:
    url = f"{API_BASE}/servers/{SERVER_ID}/resources"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=10) as resp:
                if resp.status != 200:
                    return f"ERROR ({resp.status})"

                data = await resp.json()

                attributes = data.get("attributes")
                if not attributes:
                    return "UNKNOWN"

                return attributes.get("current_state", "UNKNOWN").upper()
    except Exception:
        return "API ERROR"

# ================== HANDLERS ==================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if not allowed(message.from_user.id):
        return
    await message.answer(
        "🎮 *Play Hosting Server Control*",
        reply_markup=keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query()
async def on_callback(call: types.CallbackQuery):
    try:
        await call.answer("⏳")
    except:
        return

    if not allowed(call.from_user.id):
        return

    uid = call.from_user.id
    now = time.time()
    if uid in last_click and now - last_click[uid] < 2:
        return
    last_click[uid] = now

    if call.data == "start":
        ok = await send_power("start")
        await call.message.answer("🟢 Сервер запускается" if ok else "❌ Ошибка запуска")

    elif call.data == "stop":
        ok = await send_power("stop")
        await call.message.answer("🔴 Сервер останавливается" if ok else "❌ Ошибка остановки")

    elif call.data == "restart":
        ok = await send_power("restart")
        await call.message.answer("🔄 Сервер перезапускается" if ok else "❌ Ошибка перезапуска")

    elif call.data == "status":
        status = await get_status()
        await call.message.answer(f"📊 Статус сервера: *{status}*", parse_mode="Markdown")

# ================== MAIN ==================

async def main():
    print("🤖 Play Hosting control bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
