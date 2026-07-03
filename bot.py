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
)

# ---------- Config (Railway variables'dan) ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "packs.json"

# ---------- Bo'limlar (emoji + nom) ----------
CATEGORIES = [
    ("🎬", "Anim Texture pack"),
    ("🔞", "18+ Texture pack"),
    ("🆕", "1.21+"),
    ("🧱", "1.16+"),
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pending = {}  # admin .zip yuborganda bo'lim tanlashini kutish

WELCOME = (
    "✨ <b>Minecraft Texture Packs</b> ✨\n\n"
    "🎨 Eng zo'r texture pack'lar shu yerda!\n"
    "👇 Bo'limni tanlang:"
)

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

# ---------- Klaviaturalar (inline) ----------
def categories_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"cat:{i}")]
        for i, (emoji, name) in enumerate(CATEGORIES)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="⬅️ Orqaga", callback_data="home")

# ---------- /start ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(WELCOME, reply_markup=categories_kb())

# ---------- Bo'lim ochish (xabar JOYIDA silliq yangilanadi) ----------
@dp.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery):
    idx = int(callback.data.split(":", 1)[1])
    emoji, name = CATEGORIES[idx]
    packs = [p for p in load_packs() if p.get("category") == name]
    if not packs:
        kb = InlineKeyboardMarkup(inline_keyboard=[[back_button()]])
        await callback.message.edit_text(
            f"{emoji} <b>{name}</b>\n\n😔 Bu bo'limda hozircha pack yo'q.\n⏳ Tez orada qo'shiladi!",
            reply_markup=kb,
        )
        await callback.answer()
        return
    rows = [
        [InlineKeyboardButton(text=f"📦 {p['title']}", callback_data=f"get:{p['id']}")]
        for p in packs
    ]
    rows.append([back_button()])
    await callback.message.edit_text(
        f"{emoji} <b>{name}</b>\n\n🗂 Mavjud pack'lar: <b>{len(packs)} ta</b>\n👇 Yuklab olish uchun bosing:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()

# ---------- ⬅️ Orqaga → bosh menyu (silliq) ----------
@dp.callback_query(F.data == "home")
async def cb_home(callback: CallbackQuery):
    await callback.message.edit_text(WELCOME, reply_markup=categories_kb())
    await callback.answer()

# ---------- Pack yuklab olish ----------
@dp.callback_query(F.data.startswith("get:"))
async def cb_get(callback: CallbackQuery):
    pack_id = callback.data.split(":", 1)[1]
    pack = next((p for p in load_packs() if p["id"] == pack_id), None)
    if pack is None:
        await callback.answer("Topilmadi 😕", show_alert=True)
        return
    await callback.answer("⏳ Yuborilyapti...")
    await callback.message.answer_document(
        document=pack["file_id"],
        caption=f"📦 <b>{pack['title']}</b>\n\n✅ Marhamat! Zavqli o'yin tilaymiz! 🎮",
    )

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

# ---------- Admin: bo'lim tanlanganda saqlanadi (silliq edit) ----------
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

# ---------- Admin: /list va /remove ----------
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

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi! Railway variables'ni tekshiring.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
