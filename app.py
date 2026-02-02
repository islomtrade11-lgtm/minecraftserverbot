import asyncio
import os
import time
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from mcstatus import JavaServer

# ================== ENV ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_IDS_RAW = os.getenv("OWNER_IDS")
PLAY_API_KEY = os.getenv("PLAY_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")
MC_HOST = os.getenv("MC_HOST", "mirvosit.play.hosting")

if not all([BOT_TOKEN, OWNER_IDS_RAW, PLAY_API_KEY, SERVER_ID]):
    raise RuntimeError("Missing required environment variables")

ALLOWED_USERS = {int(x.strip()) for x in OWNER_IDS_RAW.split(",") if x.strip()}

API_BASE = "https://panel.play.hosting/api/client"

HEADERS = {
    "Authorization": f"Bearer {PLAY_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

mc_server = JavaServer.lookup(MC_HOST)

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
            InlineKeyboardButton(text="📊 Status", callback_data="status"),
            InlineKeyboardButton(text="👥 Players", callback_data="players"),
        ],
    ])

def allowed(uid: int) -> bool:
    return uid in ALLOWED_USERS

# ================== PLAY HOSTING API ==================

async def send_power(signal: str) -> bool:
    url = f"{API_BASE}/servers/{SERVER_ID}/power"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=HEADERS,
            json={"signal": signal},
            timeout=10
        ) as resp:
            text = await resp.text()
            print(f"[POWER] {signal} -> {resp.status} | {text}")
            return resp.status == 204

# ================== MC STATUS ==================

async def mc_status():
    return await asyncio.to_thread(mc_server.status)

async def mc_query():
    return await asyncio.to_thread(mc_server.query)

# ================== HANDLERS ==================

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if not allowed(message.from_user.id):
        return

    await message.answer(
        "🎮 *Minecraft Server Control*\n"
        f"🔗 `{MC_HOST}`",
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
        try:
            status = await mc_status()
            po = status.players.online
            pm = status.players.max
            ping = int(status.latency)
            motd = str(status.description).replace("\n", " ")

            text = (
                f"🟢 *Minecraft сервер*\n"
                f"📡 ONLINE\n"
                f"👥 {po}/{pm}\n"
                f"🏓 {ping} ms\n"
                f"📝 `{motd}`\n"
                f"🔗 `{MC_HOST}`"
            )
        except Exception:
            text = (
                f"🔴 *Minecraft сервер*\n"
                f"📡 OFFLINE\n"
                f"🔗 `{MC_HOST}`"
            )

        await call.message.answer(text, parse_mode="Markdown")

    elif call.data == "players":
        try:
            query = await mc_query()
            names = query.players.names
            if not names:
                text = "😴 *Сейчас на сервере никого нет*"
            else:
                text = "👥 *Игроки онлайн:*\n" + "\n".join(f"• `{n}`" for n in names)
        except Exception:
            text = "⚠️ *Список игроков недоступен*"

        await call.message.answer(text, parse_mode="Markdown")

# ================== MAIN ==================

async def main():
    print("🤖 Minecraft Play Hosting bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
