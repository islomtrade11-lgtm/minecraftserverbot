import asyncio
import os
import time
import aiohttp
from datetime import timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from mcstatus import JavaServer

# ================== ENV ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_IDS = {int(x) for x in os.getenv("OWNER_IDS", "").split(",") if x}
PLAY_API_KEY = os.getenv("PLAY_API_KEY")
SERVER_ID = os.getenv("SERVER_ID")
MC_HOST = os.getenv("MC_HOST", "mirvosit.play.hosting")

STATUS_INTERVAL = 10
AUTO_DELETE_SECONDS = 30
AUTO_OFF_SECONDS = 15 * 60

API_BASE = "https://panel.play.hosting/api/client"

HEADERS = {
    "Authorization": f"Bearer {PLAY_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# ================== STATE ==================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

mc_server = JavaServer.lookup(MC_HOST)

main_chat_id = None
main_message_id = None

auto_update_enabled = True
empty_since = None
logs = []
last_click = {}

# ================== UTILS ==================

def allowed(uid: int) -> bool:
    return uid in OWNER_IDS

def log_event(text: str):
    logs.append(f"[{time.strftime('%H:%M:%S')}] {text}")
    del logs[:-20]

async def temp_send(chat_id, text, **kwargs):
    msg = await bot.send_message(chat_id, text, **kwargs)
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    try:
        await msg.delete()
    except:
        pass

def bar(cur, max_, size=10):
    return "█" * int(size * cur / max_) + "░" * (size - int(size * cur / max_)) if max_ else ""

def fmt_time(sec):
    return str(timedelta(seconds=max(0, int(sec))))

# ================== PLAY HOSTING ==================

async def power(signal: str):
    url = f"{API_BASE}/servers/{SERVER_ID}/power"
    async with aiohttp.ClientSession() as s:
        async with s.post(url, headers=HEADERS, json={"signal": signal}) as r:
            log_event(f"{signal.upper()} → {r.status}")
            return r.status == 204

# ================== UI ==================

def keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("▶️ Start", callback_data="start"),
            InlineKeyboardButton("⏹ Stop", callback_data="stop"),
            InlineKeyboardButton("🔄 Restart", callback_data="restart"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить", callback_data="refresh"),
            InlineKeyboardButton("👥 Игроки", callback_data="players"),
        ],
        [
            InlineKeyboardButton("📜 Лог", callback_data="log"),
            InlineKeyboardButton("📌 IP", callback_data="ip"),
        ],
        [
            InlineKeyboardButton(
                f"⚙ Автообновление: {'✅' if auto_update_enabled else '❌'}",
                callback_data="auto"
            )
        ]
    ])

# ================== STATUS LOOP ==================

async def status_loop():
    global empty_since

    while True:
        await asyncio.sleep(STATUS_INTERVAL)
        if not auto_update_enabled or not main_chat_id:
            continue

        try:
            st = await asyncio.to_thread(mc_server.status)
            online = True
            po, pm = st.players.online, st.players.max
            ping = int(st.latency)
            motd = str(st.description).replace("\n", " ")
        except:
            online = False
            po = pm = ping = 0
            motd = "Offline"

        timer_text = ""
        if online and po == 0:
            if empty_since is None:
                empty_since = time.time()
            left = AUTO_OFF_SECONDS - (time.time() - empty_since)
            timer_text = f"⏳ Без игроков выключится через: `{fmt_time(left)}`"
            if left <= 0:
                await power("stop")
                empty_since = None
        else:
            empty_since = None

        text = (
            f"🟢 **Main Vanilla 1.19**\n"
            f"📡 {'ONLINE' if online else 'OFFLINE'} • 🏓 {ping} ms\n"
            f"👥 {po}/{pm} {bar(po, pm)}\n"
            f"📝 `{motd}`\n"
            f"{timer_text}\n"
            f"🌐 `{MC_HOST}`"
        )

        try:
            await bot.edit_message_text(
                chat_id=main_chat_id,
                message_id=main_message_id,
                text=text,
                reply_markup=keyboard(),
                parse_mode="Markdown"
            )
        except:
            pass

# ================== HANDLERS ==================

@dp.message(CommandStart())
async def start_cmd(msg: types.Message):
    global main_chat_id, main_message_id
    if not allowed(msg.from_user.id):
        return
    sent = await msg.answer("⏳ Загружаю статус...")
    main_chat_id = msg.chat.id
    main_message_id = sent.message_id

@dp.callback_query()
async def cb(call: types.CallbackQuery):
    if not allowed(call.from_user.id):
        return

    await call.answer()

    if call.data in ("start", "stop", "restart"):
        ok = await power(call.data)
        await temp_send(call.message.chat.id, f"{'✅' if ok else '❌'} {call.data.upper()}")

    elif call.data == "players":
        try:
            q = await asyncio.to_thread(mc_server.query)
            names = q.players.names
            text = "👥 Игроки:\n" + "\n".join(names) if names else "😴 Никого нет"
        except:
            text = "⚠️ QUERY недоступен"
        await temp_send(call.message.chat.id, text)

    elif call.data == "log":
        await temp_send(call.message.chat.id, "📜 Лог:\n" + "\n".join(logs[-10:] or ["Пусто"]))

    elif call.data == "ip":
        await temp_send(call.message.chat.id, f"`{MC_HOST}`", parse_mode="Markdown")

    elif call.data == "auto":
        global auto_update_enabled
        auto_update_enabled = not auto_update_enabled
        log_event(f"AUTO → {'ON' if auto_update_enabled else 'OFF'}")

# ================== MAIN ==================

async def main():
    asyncio.create_task(status_loop())
    print("🤖 FINAL Minecraft Control Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
