import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# ---------- Config (Railway variables'dan) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "packs.json"
# Loading sticker file_id (ixtiyoriy). Bo'sh bo'lsa "⏳ Yuklanmoqda..." matni chiqadi.
# ---------- Sticker file_id olish (vaqtincha: hammaga) ----------
@dp.message(F.sticker)
async def on_sticker(message: Message):
    await message.answer(
        "🆔 Sticker file_id:\n<code>"
        + message.sticker.file_id
        + "</code>"
    )

# ---------- Bo'limlar (emoji + nom) ----------
CATEGORIES = [
    ("🎬", "Anim Texture pack"),
    ("🔞", "18+ Texture pack"),
    ("🆕", "1.21+"),
    ("🧱", "1.16+"),
]
BACK_LABEL = "⬅️ Orqaga"
CAT_LABELS = {f"{e} {n}": n for e, n in CATEGORIES}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pending = {}        # admin .zip yuborganda bo'lim tanlashini kutish
user_category = {}  # user_id -> hozir ochilgan bo'lim
last_menu = {}      # user_id -> oxirgi menyu xabarining id'si

# ---------- Saqlash ----------
def load_packs():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_packs(packs):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8")

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def safe_delete_message(chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

async def show_menu(message: Message, text: str, kb):
    """Botning eski menyusini o'chirib, yangisini yuboradi (chat toza qoladi)."""
    uid = message.from_user.id
    await safe_delete_message(message.chat.id, message.message_id)   # tugma matnini o'chir
    old = last_menu.get(uid)
    if old:
        await safe_delete_message(message.chat.id, old)             # eski menyuni o'chir
    sent = await message.answer(text, reply_markup=kb)
    last_menu[uid] = sent.message_id

# ---------- Klaviaturalar ----------
def main_kb() -> ReplyKeyboardMarkup:
    labels = [f"{e} {n}" for e, n in CATEGORIES]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=labels[0]), KeyboardButton(text=labels[1])],
            [KeyboardButton(text=labels[2]), KeyboardButton(text=labels[3])],
        ],
        resize_keyboard=True,
    )

def packs_kb(packs) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=f"📦 {p['title']}")] for p in packs]
    rows.append([KeyboardButton(text=BACK_LABEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def back_only_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BACK_LABEL)]], resize_keyboard=True)

# ---------- /start ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_category.pop(message.from_user.id, None)
    await show_menu(
        message,
        "✨ <b>Minecraft Texture Packs</b> ✨\n\n🎨 Bo'limni tanlang 👇",
        main_kb(),
    )

# ---------- Admin: /list, /remove ----------
@dp.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    packs = load_packs()
    if not packs:
        await message.answer("📭 Ro'yxat bo'sh.")
        return
    lines = [f"🔹 <b>{p['id']}</b>. {p['title']} — <i>{p.get('category', '?')}</i>" for p in packs]
    await message.answer("📋 <b>Pack'lar:</b>\n" + "\n".join(lines) + "\n\n🗑 O'chirish: /remove ID")

@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("✏️ Foydalanish: /remove ID")
        return
    pack_id = parts[1]
    packs = load_packs()
    new_packs = [p for p in packs if p["id"] != pack_id]
    if len(new_packs) == len(packs):
        await message.answer("❌ Bunday ID yo'q.")
        return
    save_packs(new_packs)
    await message.answer(f"🗑 O'chirildi (ID {pack_id}). ✅")

# ---------- Admin: sticker file_id olish (loading sticker uchun) ----------
@dp.message(F.sticker)
async def on_sticker(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "🆔 Sticker file_id:\n<code>"
            + message.sticker.file_id
            + "</code>\n\nBuni Railway'da <b>LOADING_STICKER_ID</b> variable'ga qo'ying."
        )

# ---------- ⬅️ Orqaga ----------
@dp.message(F.text == BACK_LABEL)
async def go_back(message: Message):
    user_category.pop(message.from_user.id, None)
    await show_menu(
        message,
        "✨ <b>Minecraft Texture Packs</b> ✨\n\n🎨 Bo'limni tanlang 👇",
        main_kb(),
    )

# ---------- Bo'lim tanlash ----------
@dp.message(F.text.in_(set(CAT_LABELS.keys())))
async def open_category(message: Message):
    name = CAT_LABELS[message.text]
    user_category[message.from_user.id] = name
    packs = [p for p in load_packs() if p.get("category") == name]
    if not packs:
        await show_menu(
            message,
            f"😔 <b>{name}</b> bo'limida hozircha pack yo'q.\n⏳ Tez orada qo'shiladi!",
            back_only_kb(),
        )
        return
    await show_menu(
        message,
        f"📦 <b>{name}</b> — {len(packs)} ta pack\n👇 Yuklab olish uchun tanlang:",
        packs_kb(packs),
    )

# ---------- Pack tanlash → LOADING sticker → .zip ----------
@dp.message(F.text.startswith("📦 "))
async def send_pack(message: Message):
    await safe_delete_message(message.chat.id, message.message_id)  # bosilgan tugma matnini o'chir
    title = message.text[2:].strip()
    cat = user_category.get(message.from_user.id)
    packs = load_packs()
    pack = next(
        (p for p in packs if p["title"] == title and (cat is None or p.get("category") == cat)),
        None,
    ) or next((p for p in packs if p["title"] == title), None)
    if pack is None:
        await message.answer("😕 Bu pack topilmadi.")
        return

    # 1) Loading ko'rsat
    if LOADING_STICKER_ID:
        loading = await message.answer_sticker(LOADING_STICKER_ID)
    else:
        loading = await message.answer("⏳ <b>Yuklanmoqda...</b>")

    # 2) Faylni yubor
    await message.answer_document(
        document=pack["file_id"],
        caption=f"📦 <b>{pack['title']}</b>\n\n✅ Marhamat! Zavqli o'yin tilaymiz! 🎮",
    )

    # 3) Loading'ni o'chir
    await safe_delete_message(loading.chat.id, loading.message_id)

# ---------- Admin: .zip yuboradi → bo'lim so'raydi ----------
@dp.message(F.document)
async def on_document(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 Kechirasiz, faqat owner pack qo'sha oladi.")
        return
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".zip"):
        await message.answer("⚠️ Faqat <b>.zip</b> fayl qabul qilinadi.")
        return
    pending[message.from_user.id] = {
        "file_id": doc.file_id,
        "file_name": doc.file_name,
        "title": doc.file_name.rsplit(".zip", 1)[0],
    }
    rows = [
        [InlineKeyboardButton(text=f"{e} {n}", callback_data=f"add:{i}")]
        for i, (e, n) in enumerate(CATEGORIES)
    ]
    await message.answer(
        "📥 <b>Fayl qabul qilindi!</b>\n🗂 Qaysi bo'limga qo'shamiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )

# ---------- Admin: bo'lim tanlanganda saqlanadi ----------
@dp.callback_query(F.data.startswith("add:"))
async def cb_add(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    data = pending.get(callback.from_user.id)
    if not data:
        await callback.answer("Avval .zip fayl yuboring.", show_alert=True)
        return
    emoji, name = CATEGORIES[int(callback.data.split(":", 1)[1])]
    packs = load_packs()
    new_id = str(max([int(p["id"]) for p in packs], default=0) + 1)
    packs.append({
        "id": new_id,
        "title": data["title"],
        "file_id": data["file_id"],
        "file_name": data["file_name"],
        "category": name,
    })
    save_packs(packs)
    pending.pop(callback.from_user.id, None)
    await callback.message.edit_text(
        f"✅ <b>Muvaffaqiyatli qo'shildi!</b>\n\n📦 {data['title']}\n{emoji} Bo'lim: <b>{name}</b>"
    )
    await callback.answer("Saqlandi ✅")

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi! Railway variables'ni tekshiring.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
