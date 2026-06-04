import os
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

MAX_SPEEDTESTS = 20
CONCURRENT_SPEEDTESTS = 3

user_data_store = {}
speedtest_sem = asyncio.Semaphore(CONCURRENT_SPEEDTESTS)

async def check_proxy(proxy):
    try:
        connector = ProxyConnector.from_url(proxy)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("https://api.ipify.org?format=json", timeout=15) as r:
                data = await r.json()
                return True, data.get("ip")
    except Exception:
        return False, None

async def run_speedtest(proxy):
    async with speedtest_sem:
        proc = await asyncio.create_subprocess_exec(
            "speedtest-cli", "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "HTTP_PROXY": proxy, "HTTPS_PROXY": proxy}
        )
        out, err = await proc.communicate()
        return out.decode() if proc.returncode == 0 else err.decode()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send proxies (one per line).\nSupports:\nhttp://ip:port\nhttp://user:pass@ip:port\nsocks5://ip:port"
    )

async def handle_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    proxies = [x.strip() for x in update.message.text.splitlines() if x.strip()]
    alive = []

    msg = await update.message.reply_text("Checking proxies...")

    for p in proxies:
        ok, ip = await check_proxy(p)
        if ok:
            alive.append({"proxy": p, "ip": ip})

    if not alive:
        await msg.edit_text("No alive proxies found.")
        return

    user_data_store[update.effective_user.id] = alive

    kb = [[
        InlineKeyboardButton("Speedtest First", callback_data="first"),
        InlineKeyboardButton("Speedtest All", callback_data="all")
    ]]

    await msg.edit_text(
        f"Alive: {len(alive)}/{len(proxies)}\nRun speedtest?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    alive = user_data_store.get(q.from_user.id, [])

    if q.data == "first":
        alive = alive[:1]

    if len(alive) > MAX_SPEEDTESTS:
        alive = alive[:MAX_SPEEDTESTS]

    await q.edit_message_text("Running speedtests...")

    results = []

    for item in alive:
        result = await run_speedtest(item["proxy"])
        results.append(
            f"IP: {item['ip']}\nProxy: {item['proxy']}\n\n{result[:1500]}"
        )

    text = "\n\n====================\n\n".join(results)

    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        await context.bot.send_message(chat_id=q.message.chat_id, text=chunk)

def main():
    token = os.getenv("BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_proxies))

    app.run_polling()

if __name__ == "__main__":
    main()
