# ===============================
# 🎰 Telegram Roulette Bot (Crypto Royale)
# 👑 بواسطة JOHN OSAMA
# ===============================

import asyncio
import logging
import random
import re
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    BotCommand, Bot, MenuButtonCommands, MessageEntity
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# =========== إعداداتك الشخصية ===========
TELEGRAM_BOT_TOKEN = "8474184257:AAGR5025u_KzEf4Gywo5YH5qLb26Qf0vs_I"
TOKEN = TELEGRAM_BOT_TOKEN
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set. Please add it as a secret.")
OWNER_USERNAME = "J_O_H_N8"
BOT_DISPLAY_NAME = "Crypto Royale"
BOT_PUBLIC_LINK = "https://t.me/cryptoJohn0bot"
OWNER_CHANNEL_LINK = "https://t.me/CRYPTO2KING1"
OFFICIAL_CHANNEL_USERNAME = "@CRYPTO2KING1"
GIVEAWAYS_CHANNEL = "@CryptoRoyale10"
MAX_REPORTS = 10  # عدد البلاغات اللي تساوي 100%

DATA_FILE = "data.json"
LOG_FILE = "bot.log"
DB_FILE = "roulettes.db"

# =========== معرفات الأدمن (ضع هنا الـ user_id الخاصة بالأدمنية) ===========
ADMIN_IDS: Set[int] = set()  # مثال: {123456789, 987654321}


# =========== IDs الإيموجي المخصصة ===========
_CE = {
    "heart1": "5451714942157724312",   # 🤍 في رسالة الترحيب (Crypto Royale)
    "heart2": "5251203410396458957",   # 🤍 في الاكثر أماناً
    "id":     "5776284293571552999",   # 🆔
    "target": "5350460637182993292",   # 🎯
    "bullet": "5240379770687999291",   # 🔹
    "person": "5316887736823591263",   # 👤
    "slot":   "5102856631562011824",   # 🎰
    "quick":  "5224607267797606837",   # ⚡
    "pin":    "5391032818111363540",   # 📍
    "check1": "5206607081334906820",   # ✅ نشر الروليت السريع
    "check2": "5316827280863934685",   # ✅ تم الاختيار / الوصف
    "check3": "5118861066981344121",   # ✅ نشر الروليت العادية
    "pencil": "5458382591121964689",   # ✍️
    "warn1":  "5447644880824181073",   # ⚠️ في رسالة الوصف
    "warn2":  "5420323339723881652",   # ⚠️ في ربط قناة/جروب
    "megap":  "5267442591548320083",   # 📢
    "signal": "5256134032852278918",   # 📡
    "mappin": "5397782960512444700",   # 📌
    "left":   "5775896462319686826",   # 👈
    "bubble": "5443038326535759644",   # 💬
    "folder": "5332586662629227075",   # 🗂
    "num1":   "5440539497383087970",   # 1️⃣
    "num2":   "5447203607294265305",   # 2️⃣
    "num3":   "5453902265922376865",   # 3️⃣
}


def tge(key: str, fallback: str) -> str:
    """إرجاع HTML tag للإيموجي المخصص، يعمل مع parse_mode='HTML'"""
    eid = _CE.get(key, "")
    if not eid:
        return fallback
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'


def build_custom_emoji_message(template: str, placeholder: str = "⭐") -> tuple:
    """
    تحول نص يحتوي على [emoji:EMOJI_ID] إلى نص نظيف مع قائمة MessageEntity
    جاهزة للإرسال عبر python-telegram-bot.

    المعاملات:
        template    — النص مع placeholders بصيغة [emoji:1234567890]
        placeholder — الحرف/الإيموجي الذي يحل مكان كل placeholder (افتراضي ⭐)

    الناتج:
        (clean_text: str, entities: list[MessageEntity])

    مثال:
        text, ents = build_custom_emoji_message(
            "مرحباً [emoji:5368324170671202286] أهلاً [emoji:5357419403325481793]"
        )
        await bot.send_message(chat_id, text, entities=ents)

    مثال متعدد الإيموجي في رسالة واحدة:
        text, ents = build_custom_emoji_message(
            "[emoji:5368324170671202286] روليت سريع [emoji:5357419403325481793]",
            placeholder="🎯"
        )
        await message.reply_text(text, entities=ents)
    """
    pattern = re.compile(r'\[emoji:(\d+)\]')
    entities: list[MessageEntity] = []
    clean = ""

    last = 0
    for m in pattern.finditer(template):
        # النص قبل الـ placeholder
        clean += template[last:m.start()]
        # احسب الـ offset بوحدات UTF-16
        offset_utf16 = len(clean.encode("utf-16-le")) // 2
        # أضف حرف الـ placeholder
        clean += placeholder
        length_utf16 = len(placeholder.encode("utf-16-le")) // 2
        entities.append(MessageEntity(
            type=MessageEntity.CUSTOM_EMOJI,
            offset=offset_utf16,
            length=length_utf16,
            custom_emoji_id=m.group(1),
        ))
        last = m.end()

    clean += template[last:]
    return clean, entities


async def send_custom_emoji_msg(bot_or_message, chat_id: int, template: str,
                                 placeholder: str = "⭐", **kwargs):
    """
    دالة مختصرة ترسل رسالة تحتوي custom emojis مباشرة.

    مثال:
        await send_custom_emoji_msg(
            context.bot, chat_id,
            "🎉 مبروك الفائز [emoji:5368324170671202286]",
        )
    """
    text, entities = build_custom_emoji_message(template, placeholder)
    kwargs.setdefault("disable_web_page_preview", True)
    return await bot_or_message.send_message(
        chat_id=chat_id,
        text=text,
        entities=entities,
        **kwargs,
    )


# =========== نظام الإعدادات ===========
SETTINGS_FILE = "bot_settings.json"
DEFAULT_SETTINGS = {
    "join_btn": "👥 المشاركة",
    "stop_btn": "⏹️ إيقاف المشاركة",
    "draw_btn": "🏁 بدء السحب",
    "alert_joined": "تم الاشتراك بالسحب",
    "winners_prefix": "🎉عدد الفائزين:",
    "post_extra": "",
    "replacements": {},
    "extra_admins": [],
    "screen_welcome": f'شرفتنى يا {{first_name}} فى روليت Crypto Royale {tge("heart1","🤍")}\n\n{tge("id","🆔")} الايدى بتاعك: {{uid}}\n\nالاكثر اماناً {tge("heart2","🤍")}',
    "screen_quick_roulette": f'{tge("quick","⚡")} <b>الروليت السريع</b>\n\nاختر القناة أو الجروب اللي تريد تنشر فيه الروليت:',
    "screen_regular_roulette": f'{tge("slot","🎰")} <b>الروليت العادية</b>\n\nاختر القناة أو الجروب اللي تريد تنشر فيه الروليت:',
    "screen_description": f'{tge("pencil","✍️")} اكتب نص السحب كما تحب:',
    "screen_req_channels": "🔒 <b>هل تريد إضافة قناة شرط للاشتراك؟</b>\n\nيمكنك إضافة قناة يجب على المشارك الاشتراك فيها.",
    "screen_winners_count": f'{tge("target","🎯")} <b>كم عدد الفائزين في هذه الروليت؟</b>\n\nأرسل الرقم فقط (مثال: 1، 2، 3...)\nالحد الأقصى: 100 فائز',
    "screen_support": f'{tge("bubble","💬")} <b>الدعم الفني</b>\n\nللتواصل مع الدعم راسل:\n{tge("person","👤")} @J_O_H_N8',
    "custom_home_btns": [],
    "user_reports": {},
    "banned_users": [],
    "btn_home_quick":    "⚡ روليت سريع",
    "btn_home_regular":  "🎰 الروليت العادية",
    "btn_home_channels": "📢 القنوات",
    "btn_home_support":  "💬 الدعم",
    "btn_home_official": "📣 القناة الرسمية",
}

def load_settings() -> dict:
    if Path(SETTINGS_FILE).exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in s:
                    s[k] = v
            return s
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings(s: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    bot_settings.clear()
    bot_settings.update(s)

bot_settings = load_settings()


def is_bot_admin(user) -> bool:
    if user.username and user.username.lower() == OWNER_USERNAME.lower():
        return True
    if user.id in ADMIN_IDS:
        return True
    if user.id in bot_settings.get("extra_admins", []):
        return True
    return False


def apply_replacements(text: str) -> str:
    for old, new in bot_settings.get("replacements", {}).items():
        text = text.replace(old, new)
    return text


# =========== إنشاء قاعدة البيانات ===========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            giveaway_id TEXT PRIMARY KEY,
            roulette_key TEXT,
            owner_id INTEGER,
            channel TEXT,
            channel_title TEXT,
            required_channels TEXT,
            winners_count INTEGER,
            description TEXT,
            post_text TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            giveaway_id TEXT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at TEXT,
            PRIMARY KEY (giveaway_id, user_id)
        )
    """)
    conn.commit()
    conn.close()
    logging.info("✅ تم تهيئة قاعدة البيانات SQLite")


def db_save_giveaway(giveaway_id: str, roulette_key: str, owner_id: int,
                     channel: str, channel_title: str, required_channels: list,
                     winners_count: int, description: str, post_text: str):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO giveaways
            (giveaway_id, roulette_key, owner_id, channel, channel_title,
             required_channels, winners_count, description, post_text, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (giveaway_id, roulette_key, owner_id, channel, channel_title,
              json.dumps(required_channels, ensure_ascii=False),
              winners_count, description, post_text,
              datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ خطأ في حفظ الروليت: {e}")


def db_save_participant(giveaway_id: str, user_id: int, username: str,
                        first_name: str, last_name: str) -> bool:
    """يحفظ المشارك ويرجع True لو جديد، False لو موجود مسبقاً"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO participants
            (giveaway_id, user_id, username, first_name, last_name, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (giveaway_id, user_id, username or "", first_name or "",
              last_name or "", datetime.now().isoformat()))
        inserted = c.rowcount > 0
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        logging.error(f"❌ خطأ في حفظ المشارك: {e}")
        return False


def db_get_participants(giveaway_id: str) -> List[dict]:
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            SELECT user_id, username, first_name, last_name, joined_at
            FROM participants WHERE giveaway_id = ?
        """, (giveaway_id,))
        rows = c.fetchall()
        conn.close()
        return [{"user_id": r[0], "username": r[1], "first_name": r[2],
                 "last_name": r[3], "joined_at": r[4]} for r in rows]
    except Exception as e:
        logging.error(f"❌ خطأ في جلب المشاركين: {e}")
        return []


def db_get_giveaway(giveaway_id: str) -> dict | None:
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM giveaways WHERE giveaway_id = ?", (giveaway_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        cols = ["giveaway_id", "roulette_key", "owner_id", "channel", "channel_title",
                "required_channels", "winners_count", "description", "post_text", "active", "created_at"]
        d = dict(zip(cols, row))
        d["required_channels"] = json.loads(d["required_channels"] or "[]")
        return d
    except Exception as e:
        logging.error(f"❌ خطأ في جلب الروليت: {e}")
        return None

# =========== إعداد اللوج ===========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
)

# ======== بيانات المستخدمين ========
all_users_data: Dict[int, dict] = {}
user_first_seen: Dict[int, datetime] = {}

# ======== القنوات والجروبات المرتبطة ========
# كل مستخدم له قائمة من dict: {chat_id, username, title, type}
user_linked_channels: Dict[int, List[dict]] = {}
user_linked_groups: Dict[int, List[dict]] = {}

# ======== حالات الانتظار ========
awaiting_channel_link: Set[int] = set()
awaiting_group_link: Set[int] = set()
awaiting_roulette_description: Dict[int, bool] = {}
awaiting_required_channels: Dict[int, bool] = {}
awaiting_winners_count: Dict[int, bool] = {}

# ======== الروليتات النشطة ========
roulettes: Dict[str, dict] = {}
# ======== الروليتات المنتهية (لميزة إعادة السحب) ========
completed_roulettes: Dict[str, dict] = {}


# ======== تحميل البيانات ========
def load_data():
    global user_linked_channels, user_linked_groups, all_users_data, user_first_seen

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)

                all_users_data = {int(k): v for k, v in data.get("all_users_data", {}).items()}

                user_first_seen = {}
                for uid_str, date_str in data.get("user_first_seen", {}).items():
                    try:
                        user_first_seen[int(uid_str)] = datetime.fromisoformat(date_str)
                    except Exception:
                        user_first_seen[int(uid_str)] = datetime.now()

                # تحميل القنوات
                user_linked_channels = {int(k): v for k, v in data.get("user_linked_channels", {}).items()}
                user_linked_groups = {int(k): v for k, v in data.get("user_linked_groups", {}).items()}

                # ترحيل البيانات القديمة
                old_channels = data.get("user_linked_channel", {})
                for uid_str, ch in old_channels.items():
                    uid = int(uid_str)
                    if uid not in user_linked_channels:
                        user_linked_channels[uid] = [{"chat_id": ch, "username": ch.replace("@",""), "title": ch, "type": "channel"}]

                logging.info(f"✅ تم تحميل بيانات {len(all_users_data)} مستخدم")
            except Exception as e:
                logging.error(f"❌ خطأ في تحميل البيانات: {e}")
    else:
        logging.info("📁 ملف البيانات غير موجود، سيتم إنشاء جديد")


def save_data():
    data = {
        "all_users_data": {str(k): v for k, v in all_users_data.items()},
        "user_first_seen": {str(k): v.isoformat() for k, v in user_first_seen.items()},
        "user_linked_channels": {str(k): v for k, v in user_linked_channels.items()},
        "user_linked_groups": {str(k): v for k, v in user_linked_groups.items()},
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ تم حفظ بيانات {len(all_users_data)} مستخدم")
    except Exception as e:
        logging.error(f"❌ خطأ في حفظ البيانات: {e}")


# =========== تحديث وصف البوت بعدد المستخدمين ===========
async def update_bot_description(bot):
    try:
        total_users = len(all_users_data)
        description = f"عدد المستخدمين: {total_users:,} مستخدم نشط"
        await bot.set_my_short_description(short_description=description)
        logging.info(f"✅ تم تحديث وصف البوت: {description}")
    except Exception as e:
        logging.warning(f"⚠️ لم يتم تحديث وصف البوت: {e}")


# =========== دالة لتسجيل المستخدم ===========
async def register_user(user_id: int, username=None, first_name=None, last_name=None, context=None):
    try:
        is_new_user = False
        if user_id not in all_users_data:
            is_new_user = True
            all_users_data[user_id] = {
                "username": username or "",
                "first_name": first_name or "",
                "last_name": last_name or "",
                "first_seen": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "total_interactions": 0
            }
            user_first_seen[user_id] = datetime.now()
            logging.info(f"👤 مستخدم جديد: ID={user_id}, @{username or 'بدون'}")
            if context:
                pass  # لا يتم تحديث وصف البوت تلقائياً
        else:
            all_users_data[user_id]["last_active"] = datetime.now().isoformat()
            all_users_data[user_id]["total_interactions"] = all_users_data[user_id].get("total_interactions", 0) + 1
            if username:
                all_users_data[user_id]["username"] = username
            if first_name:
                all_users_data[user_id]["first_name"] = first_name
            if last_name is not None:
                all_users_data[user_id]["last_name"] = last_name
        save_data()
        return is_new_user
    except Exception as e:
        logging.error(f"❌ خطأ في تسجيل المستخدم: {e}")
        return False


# =========== لوحة الأزرار الرئيسية ===========
def main_keyboard():
    s = bot_settings
    rows = [
        [
            InlineKeyboardButton(s.get("btn_home_quick", "⚡ روليت سريع"), callback_data="quick_roulette"),
            InlineKeyboardButton(s.get("btn_home_regular", "🎰 الروليت العادية"), callback_data="create_regular")
        ],
        [InlineKeyboardButton(s.get("btn_home_channels", "📢 القنوات"), callback_data="channels_menu")],
        [
            InlineKeyboardButton(s.get("btn_home_support", "💬 الدعم"), callback_data="support"),
            InlineKeyboardButton(s.get("btn_home_official", "📣 القناة الرسمية"), url=OWNER_CHANNEL_LINK)
        ]
    ]
    for idx, btn in enumerate(s.get("custom_home_btns", [])):
        if btn.get("url"):
            rows.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
        else:
            rows.append([InlineKeyboardButton(btn["text"], callback_data=f"custombtn_{idx}")])
    return InlineKeyboardMarkup(rows)


# =========== /start ===========
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    is_new = await register_user(uid, user.username, user.first_name, user.last_name, context)

    first_name = user.first_name or "صديقي"

    welcome_text = bot_settings.get("screen_welcome",
        f'شرفتنى يا {{first_name}} فى روليت Crypto Royale {tge("heart1","🤍")}\n\n{tge("id","🆔")} الايدى بتاعك: {{uid}}\n\nالاكثر اماناً {tge("heart2","🤍")}'
    ).replace("{first_name}", f"<b>{first_name}</b>").replace("{uid}", f"<code>{uid}</code>")

    await update.message.reply_text(welcome_text, reply_markup=main_keyboard(), parse_mode="HTML")


# =========== زر الدعم ===========
async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        bot_settings.get("screen_support", f'{tge("bubble","💬")} <b>الدعم الفني</b>\n\nللتواصل مع الدعم راسل:\n{tge("person","👤")} @J_O_H_N8'),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📩 تواصل مع الدعم", url=f"https://t.me/{OWNER_USERNAME}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="go_home")]
        ])
    )


# =========== رجوع للرئيسية ===========
async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    first_name = q.from_user.first_name or "صديقي"
    await q.edit_message_text(
        f'شرفتنى يا <b>{first_name}</b> فى روليت Crypto Royale {tge("heart1","🤍")}\n\n'
        f'{tge("id","🆔")} الايدى بتاعك: <code>{uid}</code>\n\n'
        f'الاكثر اماناً {tge("heart2","🤍")}',
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ==========================================
# ======== قائمة القنوات ===========
# ==========================================
async def channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    channels = user_linked_channels.get(uid, [])
    groups = user_linked_groups.get(uid, [])

    text = f'{tge("megap","📢")} <b>قنواتك وجروباتك المرتبطة</b>\n\n'

    if channels:
        text += f'{tge("signal","📡")} <b>القنوات:</b>\n'
        for i, ch in enumerate(channels):
            text += f"  {i+1}. {ch['title']} (@{ch['username']})\n"
        text += "\n"
    if groups:
        text += "👥 *الجروبات:*\n"
        for i, gr in enumerate(groups):
            text += f"  {i+1}. {gr['title']} (@{gr.get('username','بدون يوزر')})\n"
        text += "\n"

    if not channels and not groups:
        text += "❌ لم تربط أي قناة أو جروب بعد.\n\n"

    text += "اختر ما تريد:"

    buttons = [
        [
            InlineKeyboardButton("🔗 ربط قناة", callback_data="link_channel"),
            InlineKeyboardButton("👥 ربط جروب", callback_data="link_group")
        ]
    ]
    if channels or groups:
        buttons.append([InlineKeyboardButton("🗑️ فصل قناة/جروب", callback_data="unlink_menu")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="go_home")])

    await q.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


# =========== ربط قناة ===========
async def link_channel_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    awaiting_channel_link.add(uid)
    bot_me = await context.bot.get_me()
    bot_username = bot_me.username or "cryptoJohn0bot"
    await q.edit_message_text(
        f'{tge("mappin","📌")} <b>ربط قناة</b>\n\n'
        f"أرسل معرف أو رابط قناتك:\n\n"
        f"• @اسم_القناة\n"
        f"• https://t.me/اسم_القناة\n\n"
        f'{tge("warn2","⚠️")} تأكد أن:\n'
        f"1. البوت مضاف كأدمن في القناة\n"
        f"2. أنت أدمن في القناة\n\n"
        f'{tge("left","👈")} لإضافة البوت: <a href="https://t.me/{bot_username}">@{bot_username}</a>',
        parse_mode="HTML"
    )


# =========== ربط جروب ===========
async def link_group_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    awaiting_group_link.add(uid)
    bot_me = await context.bot.get_me()
    bot_username = bot_me.username or "cryptoJohn0bot"
    await q.edit_message_text(
        f'{tge("mappin","📌")} <b>ربط جروب</b>\n\n'
        f"أرسل معرف أو رابط الجروب:\n\n"
        f"• @اسم_الجروب\n"
        f"• https://t.me/اسم_الجروب\n\n"
        f'{tge("warn2","⚠️")} تأكد أن:\n'
        f"1. البوت مضاف كأدمن في الجروب\n"
        f"2. أنت أدمن في الجروب\n\n"
        f'{tge("left","👈")} لإضافة البوت: <a href="https://t.me/{bot_username}">@{bot_username}</a>',
        parse_mode="HTML"
    )


# =========== قائمة فصل القنوات ===========
async def unlink_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    channels = user_linked_channels.get(uid, [])
    groups = user_linked_groups.get(uid, [])

    if not channels and not groups:
        await q.answer("❌ لا يوجد شيء لفصله.", show_alert=True)
        return

    buttons = []
    for i, ch in enumerate(channels):
        buttons.append([InlineKeyboardButton(f"❌ {ch['title']} (قناة)", callback_data=f"unlink_ch_{i}")])
    for i, gr in enumerate(groups):
        buttons.append([InlineKeyboardButton(f"❌ {gr['title']} (جروب)", callback_data=f"unlink_gr_{i}")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="channels_menu")])

    await q.edit_message_text(
        "🗑️ *اختر ما تريد فصله:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# =========== تنفيذ فصل قناة ===========
async def do_unlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data  # unlink_ch_0 or unlink_gr_0

    parts = data.split("_")
    kind = parts[1]  # ch or gr
    idx = int(parts[2])

    if kind == "ch":
        lst = user_linked_channels.get(uid, [])
        if idx < len(lst):
            removed = lst.pop(idx)
            user_linked_channels[uid] = lst
            save_data()
            await q.answer(f"✅ تم فصل {removed['title']}", show_alert=True)
    elif kind == "gr":
        lst = user_linked_groups.get(uid, [])
        if idx < len(lst):
            removed = lst.pop(idx)
            user_linked_groups[uid] = lst
            save_data()
            await q.answer(f"✅ تم فصل {removed['title']}", show_alert=True)

    # رجوع لقائمة القنوات
    await channels_menu(update, context)


# =========== استقبال ربط قناة ===========
async def receive_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()

    try:
        channel_input = _parse_chat_input(text)
        chat = await context.bot.get_chat(channel_input)

        if chat.type not in ("channel", "supergroup", "group"):
            await update.message.reply_text("❌ هذا ليس قناة. استخدم 'ربط جروب' للجروبات.")
            awaiting_channel_link.discard(uid)
            return

        if chat.type != "channel":
            await update.message.reply_text("❌ هذا جروب وليس قناة. استخدم زر 'ربط جروب'.")
            awaiting_channel_link.discard(uid)
            return

        # التحقق من صلاحيات البوت
        ok, msg = await check_admin_permissions(context.bot, chat.id, uid)
        if not ok:
            await update.message.reply_text(msg)
            awaiting_channel_link.discard(uid)
            return

        # حفظ القناة
        ch_info = {
            "chat_id": chat.id,
            "username": chat.username or str(chat.id),
            "title": chat.title or channel_input,
            "type": "channel"
        }

        lst = user_linked_channels.get(uid, [])
        # تجنب التكرار
        for existing in lst:
            if existing["chat_id"] == chat.id:
                await update.message.reply_text(f"✅ القناة {chat.title} مربوطة مسبقاً.")
                awaiting_channel_link.discard(uid)
                return

        lst.append(ch_info)
        user_linked_channels[uid] = lst
        save_data()
        awaiting_channel_link.discard(uid)

        await update.message.reply_text(
            f"✅ تم ربط القناة بنجاح: *{chat.title}*\n\n"
            "يمكنك الآن استخدام الروليت 🎰",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        error_msg = str(e)
        logging.error(f"❌ خطأ في ربط القناة: {error_msg}")
        await update.message.reply_text(_channel_error_text(error_msg))
        awaiting_channel_link.discard(uid)


# =========== استقبال ربط جروب ===========
async def receive_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()

    try:
        group_input = _parse_chat_input(text)
        chat = await context.bot.get_chat(group_input)

        if chat.type not in ("group", "supergroup"):
            await update.message.reply_text("❌ هذه قناة وليست جروب. استخدم زر 'ربط قناة'.")
            awaiting_group_link.discard(uid)
            return

        # التحقق من صلاحيات البوت
        ok, msg = await check_admin_permissions(context.bot, chat.id, uid)
        if not ok:
            await update.message.reply_text(msg)
            awaiting_group_link.discard(uid)
            return

        # حفظ الجروب
        gr_info = {
            "chat_id": chat.id,
            "username": chat.username or str(chat.id),
            "title": chat.title or group_input,
            "type": "group"
        }

        lst = user_linked_groups.get(uid, [])
        for existing in lst:
            if existing["chat_id"] == chat.id:
                await update.message.reply_text(f"✅ الجروب {chat.title} مربوط مسبقاً.")
                awaiting_group_link.discard(uid)
                return

        lst.append(gr_info)
        user_linked_groups[uid] = lst
        save_data()
        awaiting_group_link.discard(uid)

        await update.message.reply_text(
            f"✅ تم ربط الجروب بنجاح: *{chat.title}*\n\n"
            "يمكنك الآن استخدام الروليت 🎰",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        error_msg = str(e)
        logging.error(f"❌ خطأ في ربط الجروب: {error_msg}")
        await update.message.reply_text(_channel_error_text(error_msg))
        awaiting_group_link.discard(uid)


# =========== دوال مساعدة ===========
def _parse_chat_input(text: str) -> str:
    if text.startswith("https://t.me/"):
        return "@" + text.split("/")[-1]
    elif text.startswith("t.me/"):
        return "@" + text.split("/")[-1]
    elif not text.startswith("@"):
        return "@" + text
    return text.replace(" ", "")


async def check_admin_permissions(bot, chat_id, uid) -> tuple:
    """التحقق من أن البوت والمستخدم كلاهما أدمن"""
    try:
        user_member = await bot.get_chat_member(chat_id, uid)
        if user_member.status not in ("administrator", "creator"):
            return False, "❌ أنت لست أدمن في هذه القناة/الجروب!\n\nيجب أن تكون أدمن لربطها."
    except Exception:
        return False, "❌ لا يمكن التحقق من صلاحياتك.\nتأكد أن القناة/الجروب عامة وأنت أدمن فيها."

    try:
        bot_user = await bot.get_me()
        bot_member = await bot.get_chat_member(chat_id, bot_user.id)
        if bot_member.status not in ("administrator", "creator"):
            return False, "❌ البوت ليس أدمن!\n\nأضف البوت كأدمن وأعطيه صلاحية نشر الرسائل ثم حاول مرة أخرى."
    except Exception:
        return False, "❌ لا يمكن الوصول للقناة/الجروب!\n\nتأكد أن البوت مضاف كأدمن."

    return True, ""


async def check_bot_permissions(bot, chat_id) -> bool:
    try:
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat_id, bot_user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def _channel_error_text(error_msg: str) -> str:
    if "Chat not found" in error_msg:
        return "❌ القناة/الجروب غير موجودة أو البوت ليس عضو فيها!"
    elif "Not enough rights" in error_msg:
        return "❌ البوت ليس لديه صلاحيات كافية!"
    elif "Forbidden" in error_msg:
        return "❌ البوت محظور من القناة/الجروب!"
    else:
        return f"❌ خطأ: {error_msg}\n\nتأكد من صحة الرابط وصلاحيات البوت."


def _get_all_user_chats(uid: int) -> List[dict]:
    """جلب كل القنوات والجروبات المرتبطة بالمستخدم"""
    channels = user_linked_channels.get(uid, [])
    groups = user_linked_groups.get(uid, [])
    return channels + groups


def _build_roulette_post(description: str, required_channels: list, winners_count: int) -> str:
    """بناء نص الروليت بصيغة HTML"""
    parts = []
    if description:
        parts.append(description)
    parts.append(f"{bot_settings.get('winners_prefix', '🎉عدد الفائزين:')} {winners_count}")
    if required_channels:
        channels_text = ""
        for channel in required_channels:
            ch_clean = channel.replace('@', '')
            channels_text += f'👉 <a href="https://t.me/{ch_clean}">{channel}</a>\n'
        parts.append(channels_text.rstrip())
    extra = bot_settings.get("post_extra", "")
    if extra:
        parts.append(extra)
    parts.append("")
    parts.append(f'<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>')
    post_text = "\n".join(parts)
    return apply_replacements(post_text)


def _roulette_keyboard(count: int = 0) -> InlineKeyboardMarkup:
    """أزرار الروليت في القناة مبنية من الإعدادات"""
    s = bot_settings
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{s.get('join_btn', '👥 المشاركة')} ({count})", callback_data="join")],
        [InlineKeyboardButton(s.get("stop_btn", "⏹️ إيقاف المشاركة"), callback_data="stop"),
         InlineKeyboardButton(s.get("draw_btn", "🏁 بدء السحب"), callback_data="start_draw")]
    ])


async def _send_giveaway_notification(bot, uid: int, user, msg_link: str, winners_count: int):
    """إرسال إشعار لقناة السحوبات عند نشر روليت جديدة"""
    try:
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "مجهول"
        username_text = f"@{user.username}" if user.username else "—"
        text = (
            f"🎉 <b>سحب جديد</b>\n\n"
            f"عدد الفائزين: <b>{winners_count}</b>\n"
            f'بواسطة: "<b>{name}</b>"\n'
            f"user: {username_text}\n"
            f"id: <code>{uid}</code>"
        )
        await bot.send_message(
            chat_id=GIVEAWAYS_CHANNEL,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 رابط السحب", url=msg_link)],
                [InlineKeyboardButton("🚨 الإبلاغ عن السحب", callback_data=f"report_{uid}")]
            ])
        )
    except Exception as e:
        logging.warning(f"⚠️ فشل إرسال الإشعار لقناة السحوبات: {e}")


def _description_prompt_text(chat_title: str) -> str:
    custom = bot_settings.get("screen_description", "")
    if custom:
        return f'{tge("check2","✅")} تم اختيار: <b>{chat_title}</b>\n\n{custom}'
    return (
        f'{tge("check2","✅")} تم اختيار: <b>{chat_title}</b>\n\n'
        f'{tge("pencil","✍️")} اكتب نص السحب كما تحب بالتنسيق العادي من تيليجرام.\n\n'
        "يمكنك استخدام التنسيقات التالية:\n"
        "<tg-spoiler>للتشويش</tg-spoiler>\n"
        "<b>للتعريض</b>\n"
        "<i>للميلان</i>\n"
        "<u>للتسطير</u>\n"
        "<s>للتشطيب</s>\n\n"
        f'{tge("check2","✅")} نفس التنسيق اللي هتكتبه هيوصل في رسالة السحب.\n\n'
        f'{tge("warn1","⚠️")} رجاءً عدم إرسال أي روابط نهائياً'
    )


# ==========================================
# ======== الروليت السريع ===========
# ==========================================
async def quick_roulette_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid in bot_settings.get("banned_users", []):
        await q.answer("🚫 تم حظرك من إنشاء سحوبات بسبب الإبلاغات. تواصل مع الدعم.", show_alert=True)
        return

    all_chats = _get_all_user_chats(uid)

    if not all_chats:
        await q.edit_message_text(
            f'{tge("quick","⚡")} <b>الروليت السريع</b>\n\n'
            "❌ لم تربط أي قناة أو جروب بعد!\n\n"
            "اذهب لـ <b>القنوات</b> واربط قناتك أو جروبك أولاً.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 القنوات", callback_data="channels_menu")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="go_home")]
            ])
        )
        return

    buttons = []
    for chat in all_chats:
        icon = "📡" if chat["type"] == "channel" else "👥"
        buttons.append([InlineKeyboardButton(
            f"{icon} {chat['title']}",
            callback_data=f"qr_sel_{chat['chat_id']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="go_home")])

    await q.edit_message_text(
        bot_settings.get("screen_quick_roulette", f'{tge("quick","⚡")} <b>الروليت السريع</b>\n\nاختر القناة أو الجروب اللي تريد تنشر فيه الروليت:'),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def quick_roulette_select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # qr_sel_{chat_id}
    chat_id = int(q.data.split("_", 2)[2])

    # تحقق من أن هذا الشات لا يزال مربوطاً بالمستخدم
    all_chats = _get_all_user_chats(uid)
    selected = next((c for c in all_chats if c["chat_id"] == chat_id), None)

    if not selected:
        await q.answer("❌ لم يتم العثور على هذه القناة/الجروب.", show_alert=True)
        return

    # حفظ الاختيار مؤقتاً
    context.user_data["qr_chat"] = selected

    await q.edit_message_text(
        f'{tge("quick","⚡")} <b>الروليت السريع</b>\n\n'
        f'{tge("pin","📍")} القناة/الجروب: <b>{selected["title"]}</b>\n\n'
        "اختر عدد المشاركين:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5 أشخاص", callback_data="qr_cnt_5"),
                InlineKeyboardButton("10 أشخاص", callback_data="qr_cnt_10")
            ],
            [
                InlineKeyboardButton("20 شخص", callback_data="qr_cnt_20"),
                InlineKeyboardButton("30 شخص", callback_data="qr_cnt_30")
            ],
            [
                InlineKeyboardButton("50 شخص", callback_data="qr_cnt_50")
            ],
            [InlineKeyboardButton("🔙 رجوع", callback_data="quick_roulette")]
        ])
    )


async def quick_roulette_select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # qr_cnt_{count}
    max_participants = int(q.data.split("_")[2])
    selected = context.user_data.get("qr_chat")

    if not selected:
        await q.answer("❌ حدث خطأ، حاول مرة أخرى.", show_alert=True)
        return

    chat_id = selected["chat_id"]

    has_permissions = await check_bot_permissions(context.bot, chat_id)
    if not has_permissions:
        await q.edit_message_text(
            "❌ البوت لم يعد أدمن في القناة/الجروب!\n\n"
            "رجاءً أعد إضافة البوت كأدمن ثم حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="go_home")]])
        )
        return

    try:
        post_text = _build_quick_roulette_post(max_participants, 0)

        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=post_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_quick_roulette_keyboard(0, max_participants)
        )

        roulette_key = f"{sent.chat.id}:{sent.message_id}"
        giveaway_id = str(uuid.uuid4())[:8]
        roulettes[roulette_key] = {
            "giveaway_id": giveaway_id,
            "owner_id": uid,
            "participants": [],
            "active": True,
            "required_channels": [],
            "winners_count": 1,
            "max_participants": max_participants,
            "quick_roulette": True,
            "participants_data": {},
            "channel": str(chat_id),
            "channel_title": selected.get("title", ""),
            "description": "",
            "post_text": post_text,
        }
        db_save_giveaway(giveaway_id, roulette_key, uid, str(chat_id),
                         selected.get("title", ""), [], max_participants, "", post_text)

        context.user_data["last_roulette_key"] = roulette_key

        if sent.chat.username:
            msg_link = f"https://t.me/{sent.chat.username}/{sent.message_id}"
        else:
            ch_id_str = str(sent.chat.id).replace("-100", "")
            msg_link = f"https://t.me/c/{ch_id_str}/{sent.message_id}"

        await q.edit_message_text(
            f'{tge("check1","✅")} <b>تم نشر الروليت السريع!</b>\n\n'
            f'{tge("pin","📍")} في: {selected["title"]}\n'
            f'{tge("target","🎯")} عدد المقاعد: {max_participants}\n\n'
            f"سيُغلق تلقائياً ويبدأ التدوير بمجرد اكتمال المقاعد.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 رابط الروليت", url=msg_link)],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]
            ])
        )
        await _send_giveaway_notification(context.bot, uid, q.from_user, msg_link, max_participants)

    except Exception as e:
        logging.exception("خطأ في الروليت السريع")
        await q.edit_message_text(
            f"❌ خطأ في النشر: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="go_home")]])
        )


def _build_quick_roulette_post(max_p: int, count: int, participants_data: dict = None, filled: bool = False) -> str:
    """بناء نص الروليت السريع"""
    if filled and participants_data:
        full_header = bot_settings.get("ct_qr_full_header") or f"🎯 اكتملت المقاعد! ({max_p}/{max_p})"
        full_header = full_header.replace("{N}", str(max_p))
        lines = [f"<b>{full_header}</b>\n\n👥 <b>المتسابقون:</b>"]
        for i, (uid_p, data) in enumerate(participants_data.items(), 1):
            fn = data.get("first_name", "مستخدم")
            ln = data.get("last_name", "") or ""
            full = f"{fn} {ln}".strip()
            lines.append(f'{i}. <a href="tg://user?id={uid_p}">{full}</a>')
        lines.append(f'\n<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>')
        return "\n".join(lines)
    else:
        open_header = bot_settings.get("ct_qr_open_header") or f"⚡ روليت سريع — {max_p} مقعد"
        open_header = open_header.replace("{N}", str(max_p))
        open_body = bot_settings.get("ct_qr_open_body") or "اضغط الزر للانضمام! سيُغلق تلقائياً عند اكتمال المقاعد."
        text = (
            f"<b>{open_header}</b>\n\n"
            f"👥 المشاركون: {count}/{max_p}\n\n"
            f"{open_body}\n\n"
            f'<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>'
        )
        return text


def _quick_roulette_keyboard(count: int, max_p: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ الانضمام ({count}/{max_p})", callback_data="join")]
    ])


# ==========================================
# ======== الروليت العادية ===========
# ==========================================
async def create_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if uid in bot_settings.get("banned_users", []):
        await q.answer("🚫 تم حظرك من إنشاء سحوبات بسبب الإبلاغات. تواصل مع الدعم.", show_alert=True)
        return

    all_chats = _get_all_user_chats(uid)

    if not all_chats:
        await q.edit_message_text(
            "🎰 *الروليت العادية*\n\n"
            "❌ لم تربط أي قناة أو جروب بعد!\n\n"
            "اذهب لـ *القنوات* واربط قناتك أو جروبك أولاً.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 القنوات", callback_data="channels_menu")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="go_home")]
            ])
        )
        return

    buttons = []
    for chat in all_chats:
        icon = "📡" if chat["type"] == "channel" else "👥"
        buttons.append([InlineKeyboardButton(
            f"{icon} {chat['title']}",
            callback_data=f"rr_sel_{chat['chat_id']}"
        )])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="go_home")])

    await q.edit_message_text(
        bot_settings.get("screen_regular_roulette", f'{tge("slot","🎰")} <b>الروليت العادية</b>\n\nاختر القناة أو الجروب اللي تريد تنشر فيه الروليت:'),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def regular_roulette_select_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    # rr_sel_{chat_id}
    chat_id = int(q.data.split("_", 2)[2])
    all_chats = _get_all_user_chats(uid)
    selected = next((c for c in all_chats if c["chat_id"] == chat_id), None)

    if not selected:
        await q.answer("❌ لم يتم العثور على هذه القناة/الجروب.", show_alert=True)
        return

    # تحقق من صلاحيات البوت
    has_permissions = await check_bot_permissions(context.bot, chat_id)
    if not has_permissions:
        await q.edit_message_text(
            "❌ البوت لم يعد أدمن في هذه القناة/الجروب!\n\n"
            "رجاءً أعد إضافة البوت كأدمن ثم حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="create_regular")]
            ])
        )
        return

    context.user_data["rr_chat"] = selected
    context.user_data.pop("roulette_description", None)
    context.user_data.pop("required_channels", None)
    context.user_data.pop("winners_count", None)

    # طلب النص/الوصف
    awaiting_roulette_description[uid] = True
    await q.edit_message_text(
        _description_prompt_text(selected['title']),
        parse_mode="HTML"
    )


# =========== استقبال وصف الروليت ===========
async def handle_description_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "add_req_channel":
        awaiting_required_channels[uid] = True
        context.user_data.setdefault("required_channels", [])
        await q.edit_message_text(
            "📌 أرسل الآن معرف القناة الشرطية (يجب أن يكون البوت أدمن فيها):"
        )

    elif q.data == "skip_req_channel":
        context.user_data.setdefault("required_channels", [])
        await ask_winners_count(uid, context)

    elif q.data == "back_to_description":
        awaiting_roulette_description[uid] = True
        context.user_data.pop("roulette_description", None)
        selected = context.user_data.get("rr_chat", {})
        await context.bot.send_message(
            uid,
            _description_prompt_text(selected.get("title", "القناة")),
            parse_mode="HTML"
        )

    elif q.data == "add_more_channels":
        awaiting_required_channels[uid] = True
        await q.edit_message_text("📌 أرسل معرف القناة الإضافية:")

    elif q.data == "finish_channels":
        if uid in awaiting_required_channels:
            del awaiting_required_channels[uid]
        await ask_winners_count(uid, context)


# =========== سؤال عن القنوات الشرطية ===========
async def ask_about_required_channels(uid, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("required_channels", [])
    await context.bot.send_message(
        uid,
        bot_settings.get("screen_req_channels", "🔒 *هل تريد إضافة قناة شرط للاشتراك؟*\n\nيمكنك إضافة قناة يجب على المشارك الاشتراك فيها."),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ إضافة قناة", callback_data="add_req_channel")],
            [InlineKeyboardButton("⏭️ تخطي", callback_data="skip_req_channel")],
            [InlineKeyboardButton("🔙 رجوع للنص", callback_data="back_to_description")]
        ])
    )


# =========== سؤال عن عدد الفائزين ===========
async def ask_winners_count(uid, context: ContextTypes.DEFAULT_TYPE):
    awaiting_winners_count[uid] = True
    await context.bot.send_message(
        uid,
        bot_settings.get("screen_winners_count",
            f'{tge("target","🎯")} <b>كم عدد الفائزين في هذه الروليت؟</b>\n\nأرسل الرقم فقط (مثال: 1، 2، 3...)\nالحد الأقصى: 100 فائز'),
        parse_mode="HTML"
    )


# =========== إعادة نشر الروليت ===========
async def republish_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    old_key = context.user_data.get("last_roulette_key")
    chat_id = context.user_data.get("last_roulette_chat_id")

    if not old_key or not chat_id:
        await q.answer("❌ لا توجد روليت سابقة لإعادة نشرها.", show_alert=True)
        return

    # جلب بيانات الروليت القديمة
    old_roulette = roulettes.get(old_key)
    if not old_roulette:
        await q.answer("❌ انتهت صلاحية الروليت القديمة.", show_alert=True)
        return

    description = old_roulette.get("description", "")
    required_channels = old_roulette.get("required_channels", [])
    winners_count = old_roulette.get("winners_count", 1)
    post_text = old_roulette.get("post_text") or _build_roulette_post(description, required_channels, winners_count)

    # التحقق من صلاحيات البوت
    has_permissions = await check_bot_permissions(context.bot, chat_id)
    if not has_permissions:
        await q.edit_message_text(
            "❌ البوت لم يعد أدمن في القناة/الجروب!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]])
        )
        return

    try:
        # مسح الرسالة القديمة
        old_chat_id, old_msg_id = old_key.split(":")
        try:
            await context.bot.delete_message(int(old_chat_id), int(old_msg_id))
        except Exception:
            pass  # ربما حُذفت مسبقاً

        # إزالة الروليت القديمة
        roulettes.pop(old_key, None)

        # نشر روليت جديدة
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=post_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_roulette_keyboard(0)
        )

        new_key = f"{sent.chat.id}:{sent.message_id}"
        ch_title = context.user_data.get("rr_chat", {}).get("title", "") or context.user_data.get("qr_chat", {}).get("title", "")
        new_giveaway_id = str(uuid.uuid4())[:8]
        roulettes[new_key] = {
            "giveaway_id": new_giveaway_id,
            "owner_id": uid,
            "participants": [],
            "active": True,
            "required_channels": required_channels,
            "winners_count": winners_count,
            "participants_data": {},
            "channel": str(chat_id),
            "channel_title": ch_title,
            "description": description,
            "post_text": post_text,
        }
        db_save_giveaway(new_giveaway_id, new_key, uid, str(chat_id),
                         ch_title, required_channels, winners_count, description, post_text)

        context.user_data["last_roulette_key"] = new_key

        if sent.chat.username:
            msg_link = f"https://t.me/{sent.chat.username}/{sent.message_id}"
        else:
            ch_id_str = str(sent.chat.id).replace("-100", "")
            msg_link = f"https://t.me/c/{ch_id_str}/{sent.message_id}"

        await q.edit_message_text(
            "✅ <b>تم إعادة نشر الروليت بنجاح! 🎰</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 رابط الروليت", url=msg_link)],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]
            ])
        )

    except Exception as e:
        logging.exception("خطأ في إعادة النشر")
        await q.edit_message_text(
            f"❌ خطأ في إعادة النشر: {e}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]])
        )


# =========== نشر الروليت العادية ===========
async def publish_roulette(uid, context: ContextTypes.DEFAULT_TYPE):
    try:
        description = context.user_data.get("roulette_description", "")
        required_channels = context.user_data.get("required_channels", [])
        winners_count = context.user_data.get("winners_count", 1)
        selected_chat = context.user_data.get("rr_chat")

        if not selected_chat:
            await context.bot.send_message(uid, "❌ حدث خطأ، حاول مرة أخرى من البداية.")
            return

        chat_id = selected_chat["chat_id"]

        has_permissions = await check_bot_permissions(context.bot, chat_id)
        if not has_permissions:
            await context.bot.send_message(uid, "❌ البوت لم يعد أدمن في القناة/الجروب!\n\nرجاءً أعد ربطها.")
            return

        post_text = _build_roulette_post(description, required_channels, winners_count)

        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=post_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_roulette_keyboard(0)
        )

        roulette_key = f"{sent.chat.id}:{sent.message_id}"
        giveaway_id = str(uuid.uuid4())[:8]
        roulettes[roulette_key] = {
            "giveaway_id": giveaway_id,
            "owner_id": uid,
            "participants": [],
            "active": True,
            "required_channels": required_channels,
            "winners_count": winners_count,
            "participants_data": {},
            "channel": str(chat_id),
            "channel_title": selected_chat.get("title", ""),
            "description": description,
            "post_text": post_text,
        }
        db_save_giveaway(giveaway_id, roulette_key, uid, str(chat_id),
                         selected_chat.get("title", ""), required_channels,
                         winners_count, description, post_text)

        # حفظ مفتاح الروليت للإعادة لاحقاً
        context.user_data["last_roulette_key"] = roulette_key
        context.user_data["last_roulette_chat_id"] = chat_id

        if sent.chat.username:
            msg_link = f"https://t.me/{sent.chat.username}/{sent.message_id}"
        else:
            ch_id_str = str(sent.chat.id).replace("-100", "")
            msg_link = f"https://t.me/c/{ch_id_str}/{sent.message_id}"

        await context.bot.send_message(
            uid,
            f'{tge("check3","✅")} <b>تم نشر الروليت بنجاح! {tge("slot","🎰")}</b>',
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 رابط الروليت", url=msg_link)],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="go_home")]
            ])
        )
        u_data = all_users_data.get(uid, {})
        class _FakeUser:
            first_name = u_data.get("first_name", "")
            last_name  = u_data.get("last_name", "")
            username   = u_data.get("username", "")
        await _send_giveaway_notification(context.bot, uid, _FakeUser(), msg_link, winners_count)

    except Exception as e:
        logging.exception("خطأ أثناء النشر")
        await context.bot.send_message(uid, f"❌ خطأ أثناء النشر: {e}")


# =========== استقبال جميع الرسائل النصية ===========
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text.strip()

    await register_user(
        uid,
        update.message.from_user.username,
        update.message.from_user.first_name,
        update.message.from_user.last_name,
        context
    )

    logging.info(f"📨 رسالة من {uid}: {text}")

    if await admin_message_handler(update, context):
        return

    if await handle_redraw_message(update, context):
        return

    if uid in awaiting_channel_link:
        await receive_channel(update, context)
        return

    if uid in awaiting_group_link:
        await receive_group(update, context)
        return

    if uid in awaiting_roulette_description:
        # حفظ النص مع التنسيق الأصلي كـ HTML
        context.user_data["roulette_description"] = update.message.text_html
        del awaiting_roulette_description[uid]
        await ask_about_required_channels(uid, context)
        return

    if uid in awaiting_required_channels:
        try:
            channel_input = _parse_chat_input(text)
            chat = await context.bot.get_chat(channel_input)
            has_permissions = await check_bot_permissions(context.bot, chat.id)
            if not has_permissions:
                await update.message.reply_text(
                    f"❌ البوت ليس أدمن في {channel_input}!\n\n"
                    "يجب أن يكون البوت أدمن في القناة الشرطية."
                )
                return

            channel_username = f"@{chat.username}" if chat.username else str(chat.id)
            context.user_data.setdefault("required_channels", [])
            context.user_data["required_channels"].append(channel_username)

            await update.message.reply_text(
                f"✅ تم إضافة القناة: {channel_username}\n\n"
                "هل تريد إضافة قنوات أخرى؟",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ إضافة قناة أخرى", callback_data="add_more_channels"),
                     InlineKeyboardButton("❌ لا", callback_data="finish_channels")]
                ])
            )
            awaiting_required_channels.pop(uid, None)
        except Exception:
            await update.message.reply_text("❌ لا يمكن الوصول للقناة. تأكد أن البوت أدمن فيها.")
        return

    if uid in awaiting_winners_count:
        try:
            winners_count = int(text)
            if winners_count < 1:
                await update.message.reply_text("❌ عدد الفائزين يجب أن يكون 1 على الأقل.")
                return
            if winners_count > 100:
                await update.message.reply_text("❌ الحد الأقصى هو 100 فائز.")
                return
            context.user_data["winners_count"] = winners_count
            del awaiting_winners_count[uid]
            await publish_roulette(uid, context)
        except ValueError:
            await update.message.reply_text("❌ أرسل رقم صحيح فقط (مثال: 1، 2، 3)")
        return

    await update.message.reply_text("❌ لم أفهم طلبك. استخدم الأزرار في القائمة الرئيسية.", reply_markup=main_keyboard())


# =========== أزرار الروليت (المشاركة/السحب) ===========
async def handle_roulette_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    uid = q.from_user.id
    key = f"{q.message.chat.id}:{q.message.message_id}"

    if key not in roulettes:
        await q.answer("⚠️ الروليت غير موجود.", show_alert=True)
        return

    r = roulettes[key]

    if data == "join":
        if not r["active"]:
            await q.answer("❌ المشاركة مغلقة.", show_alert=True)
            return
        if uid in r["participants"]:
            await q.answer("✅ أنت مشارك بالفعل!", show_alert=True)
            return

        # التحقق الإجباري من اشتراك المستخدم في القناة/الجروب اللي نزل فيها الروليت
        roulette_chat_id = r.get("channel")
        if roulette_chat_id:
            try:
                host_member = await context.bot.get_chat_member(int(roulette_chat_id), uid)
                if host_member.status not in ("member", "administrator", "creator"):
                    await q.answer(
                        "❌ يجب أن تكون عضواً في هذه القناة/الجروب للمشاركة في الروليت.",
                        show_alert=True
                    )
                    return
            except Exception:
                await q.answer(
                    "❌ يجب أن تكون عضواً في هذه القناة/الجروب للمشاركة في الروليت.",
                    show_alert=True
                )
                return

        # التحقق من اشتراك المستخدم في القنوات الشرط الإضافية
        required_channels = r.get("required_channels", [])
        not_joined = []
        for channel in required_channels:
            try:
                member = await context.bot.get_chat_member(channel, uid)
                if member.status not in ("member", "administrator", "creator"):
                    not_joined.append(channel)
            except Exception:
                not_joined.append(channel)

        if not_joined:
            channels_list = "\n".join(not_joined)
            await q.answer(
                f"❌ يجب الاشتراك في القنوات التالية أولاً:\n{channels_list}",
                show_alert=True
            )
            return

        r["participants"].append(uid)
        try:
            user = await context.bot.get_chat(uid)
            r["participants_data"][uid] = {
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        except Exception:
            r["participants_data"][uid] = {"username": None, "first_name": "مستخدم", "last_name": None}

        # حفظ المشارك في قاعدة البيانات
        giveaway_id = r.get("giveaway_id", key)
        pdata = r["participants_data"][uid]
        db_save_participant(giveaway_id, uid, pdata.get("username") or "",
                            pdata.get("first_name") or "", pdata.get("last_name") or "")

        count = len(r["participants"])

        # ===== الروليت السريع: تحقق من اكتمال المقاعد =====
        if r.get("quick_roulette"):
            max_p = r.get("max_participants", 10)
            # تحديث نص الرسالة بعدد المشاركين الجديد
            try:
                if count < max_p:
                    await context.bot.edit_message_text(
                        chat_id=q.message.chat.id,
                        message_id=q.message.message_id,
                        text=_build_quick_roulette_post(max_p, count),
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=_quick_roulette_keyboard(count, max_p)
                    )
                else:
                    # اكتملت المقاعد — أغلق وأظهر المتسابقين بدون أزرار في القناة
                    r["active"] = False
                    gid = r.get("giveaway_id", "")
                    filled_text = _build_quick_roulette_post(max_p, count, r["participants_data"], filled=True)
                    await context.bot.edit_message_text(
                        chat_id=q.message.chat.id,
                        message_id=q.message.message_id,
                        text=filled_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("تدوير سريع", callback_data=f"qrspin_fast_{gid}"),
                                InlineKeyboardButton("تدوير بطيء", callback_data=f"qrspin_slow_{gid}")
                            ]
                        ])
                    )
                    # حفظ بيانات الروليت السريع المنتهي
                    completed_roulettes[gid] = {
                        "owner_id": r["owner_id"],
                        "winners": [],
                        "valid_participants": list(r["participants"]),
                        "participants_data": dict(r["participants_data"]),
                        "winners_count": 1,
                        "excluded_participants": [],
                        "chat_id": q.message.chat.id,
                        "result_msg_id": q.message.message_id,
                        "quick_roulette": True,
                        "max_participants": max_p,
                    }
                    del roulettes[key]
            except Exception as e:
                logging.warning(f"خطأ في تحديث رسالة الروليت السريع: {e}")
        else:
            kb = _roulette_keyboard(count)
            try:
                await context.bot.edit_message_reply_markup(q.message.chat.id, q.message.message_id, reply_markup=kb)
            except Exception:
                pass

        # إظهار popup alert للشخص اللي انضم
        channel_title = r.get("channel_title", "")
        if not channel_title:
            try:
                chat_info = await context.bot.get_chat(int(r["channel"]))
                channel_title = chat_info.title or ""
                r["channel_title"] = channel_title
            except Exception:
                channel_title = ""
        joined_msg = bot_settings.get("alert_joined", "تم الاشتراك بالسحب")
        alert_text = f"{channel_title}\n{joined_msg}" if channel_title else joined_msg
        await q.answer(alert_text, show_alert=True)

        owner_id = r["owner_id"]
        user_info = r["participants_data"][uid]
        if user_info['username']:
            name_with_link = f"[{user_info['first_name']} {user_info.get('last_name', '') or ''}](https://t.me/{user_info['username']})".strip()
            user_display = name_with_link
        else:
            user_display = f"{user_info['first_name']} {user_info.get('last_name', '') or ''}".strip()

        notification_text = (
            "🆕 مشارك جديد في الروليت:\n"
            f"👤 المستخدم: {user_display}\n"
            f"🆔 الأيدي: `{uid}`\n\n"
            f"📊 إجمالي المشاركين: {count}"
        )
        try:
            await context.bot.send_message(
                owner_id,
                notification_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚫 استبعاد المتسابق", callback_data=f"remove_{uid}_{key}")]
                ])
            )
        except Exception:
            pass

    elif data == "stop" and uid == r["owner_id"]:
        r["active"] = False
        await q.answer("⏹️ تم إيقاف المشاركة.")

    elif data == "start_draw" and uid == r["owner_id"]:
        if r["active"]:
            await q.answer("⚠️ أوقف المشاركة أولاً قبل بدء السحب.", show_alert=True)
            return

        if not r["participants"]:
            await q.answer("⚠️ لا يوجد مشاركين.", show_alert=True)
            return

        # إعادة التحقق من القنوات الشرط لكل المشاركين قبل السحب
        required_channels = r.get("required_channels", [])
        roulette_chat_id_draw = r.get("channel")
        # يشمل القناة المضيفة + القنوات الشرط الإضافية
        all_channels_to_check = []
        if roulette_chat_id_draw:
            all_channels_to_check.append(int(roulette_chat_id_draw))
        all_channels_to_check += required_channels
        valid_participants = []
        excluded_participants = []

        for p_id in r["participants"]:
            still_member = True
            for channel in all_channels_to_check:
                try:
                    member = await context.bot.get_chat_member(channel, p_id)
                    if member.status not in ("member", "administrator", "creator"):
                        still_member = False
                        break
                except Exception:
                    still_member = False
                    break
            if still_member:
                valid_participants.append(p_id)
            else:
                excluded_participants.append(p_id)

        winners_count = r.get("winners_count", 1)
        if len(valid_participants) < winners_count:
            await q.answer(
                f"⚠️ عدد المشاركين المؤهلين ({len(valid_participants)}) أقل من عدد الفائزين ({winners_count}).",
                show_alert=True
            )
            return

        winners = random.sample(valid_participants, winners_count)
        _rw_header = bot_settings.get("ct_roulette_winner") or "🎉 تم انتهاء السحب وتم اختيار الفائزين:"
        winners_text = f"<b>{_rw_header}</b>\n\n"
        for i, winner_id in enumerate(winners, 1):
            winner_data = r["participants_data"].get(winner_id, {})
            first_name = winner_data.get("first_name", "مستخدم")
            last_name = winner_data.get("last_name", "") or ""
            full_name = f"{first_name} {last_name}".strip()
            winners_text += f'{i}. <a href="tg://user?id={winner_id}">{full_name}</a>\n'

        if excluded_participants:
            winners_text += "\n⚠️ <b>ملاحظة:</b> بعض المشاركين تم استبعادهم من السحب لتركهم القنوات المطلوبه:\n"
            for ex_id in excluded_participants:
                ex_data = r["participants_data"].get(ex_id, {})
                ex_first = ex_data.get("first_name", "مستخدم")
                ex_last = ex_data.get("last_name", "") or ""
                ex_name = f"{ex_first} {ex_last}".strip()
                winners_text += f'<a href="tg://user?id={ex_id}">{ex_name}</a>\n'

        winners_text += f'\n<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>'

        # حذف البوست الأصلي من القناة
        try:
            chat_id_post, msg_id_post = key.split(":")
            await context.bot.delete_message(int(chat_id_post), int(msg_id_post))
        except Exception:
            pass

        giveaway_id = r.get("giveaway_id", key.replace(":", "_"))
        result_msg = await context.bot.send_message(
            q.message.chat.id,
            winners_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 اسحب فائز آخر", callback_data=f"redraw_{giveaway_id}")]
            ])
        )

        completed_roulettes[giveaway_id] = {
            "owner_id": uid,
            "winners": list(winners),
            "valid_participants": list(valid_participants),
            "participants_data": dict(r["participants_data"]),
            "winners_count": winners_count,
            "excluded_participants": list(excluded_participants),
            "chat_id": result_msg.chat.id,
            "result_msg_id": result_msg.message_id,
        }

        del roulettes[key]
        await q.answer("تم اختيار الفائزين 🎉")

    elif data.startswith("remove_"):
        parts = data.split("_")
        if len(parts) >= 3:
            user_to_remove = int(parts[1])
            roulette_key = "_".join(parts[2:])
            if roulette_key in roulettes and uid == roulettes[roulette_key]["owner_id"]:
                if user_to_remove in roulettes[roulette_key]["participants"]:
                    roulettes[roulette_key]["participants"].remove(user_to_remove)
                    if user_to_remove in roulettes[roulette_key]["participants_data"]:
                        del roulettes[roulette_key]["participants_data"][user_to_remove]
                    count = len(roulettes[roulette_key]["participants"])
                    kb = _roulette_keyboard(count)
                    try:
                        await context.bot.edit_message_reply_markup(
                            int(roulette_key.split(":")[0]),
                            int(roulette_key.split(":")[1]),
                            reply_markup=kb
                        )
                    except Exception:
                        pass
                    await q.answer("✅ تم استبعاد المتسابق")
                    await q.edit_message_text("✅ تم استبعاد المتسابق بنجاح")
                else:
                    await q.answer("❌ المتسابق غير موجود في القائمة")
            else:
                await q.answer("❌ ليس لديك صلاحية لهذا الإجراء")


# =========== دالة مساعدة: التحقق من صلاحيات الأدمن ===========
def is_admin(uid: int, owner_id: int) -> bool:
    return uid == owner_id or uid in ADMIN_IDS


# =========== /draw_winner <giveaway_id> ===========
async def draw_winner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❌ استخدم الأمر هكذا:\n/draw_winner <giveaway_id>\n\n"
            "مثال: /draw_winner a3f1b2c4"
        )
        return

    giveaway_id = context.args[0]
    gd = db_get_giveaway(giveaway_id)
    if not gd:
        await update.message.reply_text("❌ لم يتم العثور على السحب بهذا الـ ID.")
        return

    if not is_admin(uid, gd["owner_id"]):
        await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
        return

    participants = db_get_participants(giveaway_id)
    if not participants:
        await update.message.reply_text("⚠️ لا يوجد مشاركين في هذا السحب.")
        return

    winners_count = gd.get("winners_count", 1)
    if len(participants) < winners_count:
        await update.message.reply_text(
            f"⚠️ عدد المشاركين ({len(participants)}) أقل من عدد الفائزين المطلوب ({winners_count})."
        )
        return

    winners = random.sample(participants, winners_count)
    text = f"🎉 <b>نتيجة السحب #{giveaway_id}</b>\n\n"
    text += f"👥 إجمالي المشاركين: {len(participants)}\n\n"
    text += "🏆 <b>الفائزون:</b>\n"
    for i, w in enumerate(winners, 1):
        name = f"{w['first_name']} {w['last_name'] or ''}".strip()
        if w['username']:
            text += f'{i}. <a href="tg://user?id={w["user_id"]}">{name}</a> (@{w["username"]})\n'
        else:
            text += f'{i}. <a href="tg://user?id={w["user_id"]}">{name}</a>\n'

    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


# =========== /repost_giveaway <giveaway_id> ===========
async def repost_giveaway_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "❌ استخدم الأمر هكذا:\n/repost_giveaway <giveaway_id>\n\n"
            "مثال: /repost_giveaway a3f1b2c4"
        )
        return

    giveaway_id = context.args[0]
    gd = db_get_giveaway(giveaway_id)
    if not gd:
        await update.message.reply_text("❌ لم يتم العثور على السحب بهذا الـ ID.")
        return

    if not is_admin(uid, gd["owner_id"]):
        await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
        return

    participants = db_get_participants(giveaway_id)
    count = len(participants)
    channel_id = int(gd["channel"])

    has_permissions = await check_bot_permissions(context.bot, channel_id)
    if not has_permissions:
        await update.message.reply_text("❌ البوت لم يعد أدمن في القناة/الجروب!")
        return

    post_text = gd.get("post_text", "")
    try:
        sent = await context.bot.send_message(
            chat_id=channel_id,
            text=post_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_roulette_keyboard(count)
        )

        new_key = f"{sent.chat.id}:{sent.message_id}"
        new_giveaway_id = str(uuid.uuid4())[:8]

        # استرجاع المشاركين القدامى في الذاكرة
        p_ids = [p["user_id"] for p in participants]
        p_data = {p["user_id"]: {"username": p["username"],
                                  "first_name": p["first_name"],
                                  "last_name": p["last_name"]} for p in participants}

        roulettes[new_key] = {
            "giveaway_id": new_giveaway_id,
            "owner_id": gd["owner_id"],
            "participants": p_ids,
            "active": True,
            "required_channels": gd["required_channels"],
            "winners_count": gd["winners_count"],
            "participants_data": p_data,
            "channel": gd["channel"],
            "channel_title": gd["channel_title"],
            "description": gd["description"],
            "post_text": post_text,
        }

        # حفظ السحب الجديد مع نقل المشاركين القدامى
        db_save_giveaway(new_giveaway_id, new_key, gd["owner_id"], gd["channel"],
                         gd["channel_title"], gd["required_channels"],
                         gd["winners_count"], gd["description"], post_text)
        for p in participants:
            db_save_participant(new_giveaway_id, p["user_id"], p["username"],
                                p["first_name"], p["last_name"])

        await update.message.reply_text(
            f"✅ <b>تم إعادة نشر السحب بنجاح!</b>\n\n"
            f"🆔 ID الجديد: <code>{new_giveaway_id}</code>\n"
            f"👥 المشاركون المنقولون: {count}",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.exception("خطأ في إعادة نشر السحب")
        await update.message.reply_text(f"❌ خطأ: {e}")


# =========== /schedule_repost <giveaway_id> <YYYY-MM-DD HH:MM> ===========
async def schedule_repost_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ استخدم الأمر هكذا:\n"
            "/schedule_repost <giveaway_id> <YYYY-MM-DD> <HH:MM>\n\n"
            "مثال: /schedule_repost a3f1b2c4 2026-04-20 18:00"
        )
        return

    giveaway_id = context.args[0]
    date_str = context.args[1]
    time_str = context.args[2]

    gd = db_get_giveaway(giveaway_id)
    if not gd:
        await update.message.reply_text("❌ لم يتم العثور على السحب بهذا الـ ID.")
        return

    if not is_admin(uid, gd["owner_id"]):
        await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
        return

    try:
        scheduled_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ صيغة التاريخ غير صحيحة. استخدم: YYYY-MM-DD HH:MM")
        return

    if scheduled_dt <= datetime.now():
        await update.message.reply_text("❌ الوقت المحدد في الماضي! اختر وقتاً في المستقبل.")
        return

    async def do_scheduled_repost(ctx):
        gd_fresh = db_get_giveaway(giveaway_id)
        if not gd_fresh:
            return
        participants = db_get_participants(giveaway_id)
        count = len(participants)
        channel_id = int(gd_fresh["channel"])
        try:
            sent = await ctx.bot.send_message(
                chat_id=channel_id,
                text=gd_fresh.get("post_text", ""),
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=_roulette_keyboard(count)
            )
            new_key = f"{sent.chat.id}:{sent.message_id}"
            new_gid = str(uuid.uuid4())[:8]
            p_ids = [p["user_id"] for p in participants]
            p_data = {p["user_id"]: {"username": p["username"],
                                      "first_name": p["first_name"],
                                      "last_name": p["last_name"]} for p in participants}
            roulettes[new_key] = {
                "giveaway_id": new_gid,
                "owner_id": gd_fresh["owner_id"],
                "participants": p_ids,
                "active": True,
                "required_channels": gd_fresh["required_channels"],
                "winners_count": gd_fresh["winners_count"],
                "participants_data": p_data,
                "channel": gd_fresh["channel"],
                "channel_title": gd_fresh["channel_title"],
                "description": gd_fresh["description"],
                "post_text": gd_fresh.get("post_text", ""),
            }
            db_save_giveaway(new_gid, new_key, gd_fresh["owner_id"], gd_fresh["channel"],
                             gd_fresh["channel_title"], gd_fresh["required_channels"],
                             gd_fresh["winners_count"], gd_fresh["description"],
                             gd_fresh.get("post_text", ""))
            for p in participants:
                db_save_participant(new_gid, p["user_id"], p["username"],
                                    p["first_name"], p["last_name"])
            logging.info(f"✅ تم إعادة النشر المجدول للسحب {giveaway_id}")
        except Exception as e:
            logging.error(f"❌ خطأ في النشر المجدول: {e}")

    context.job_queue.run_once(do_scheduled_repost, when=scheduled_dt, name=f"repost_{giveaway_id}")

    await update.message.reply_text(
        f"✅ <b>تم جدولة إعادة النشر!</b>\n\n"
        f"🆔 السحب: <code>{giveaway_id}</code>\n"
        f"📅 الموعد: {scheduled_dt.strftime('%Y-%m-%d %H:%M')}",
        parse_mode="HTML"
    )


# =========== أمر /users - عرض عدد المستخدمين ===========
async def users_count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(all_users_data)
    await update.message.reply_text(f"👥 عدد المستخدمين: {total:,} مستخدم")


# =========== إحصائيات المستخدمين (للأدمن) ===========
async def عدد_المستخدمين(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        total_users = len(all_users_data)
        if total_users == 0:
            await update.message.reply_text("📊 لا يوجد مستخدمين مسجلين حتى الآن.")
            return

        active_users = 0
        week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
        for uid, udata in all_users_data.items():
            last_active = datetime.fromisoformat(udata.get("last_active", datetime.now().isoformat()))
            if last_active.timestamp() > week_ago:
                active_users += 1

        total_channels = sum(len(v) for v in user_linked_channels.values())
        total_groups = sum(len(v) for v in user_linked_groups.values())

        today_users = 0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for uid, fs in user_first_seen.items():
            if fs >= today_start:
                today_users += 1

        stats_text = f"""
📊 *إحصائيات المستخدمين*

👥 *إجمالي المستخدمين:* {total_users:,}
✅ *المستخدمين النشطين (أسبوع):* {active_users:,}
🆕 *مستخدمين جدد اليوم:* {today_users:,}
📡 *قنوات مرتبطة:* {total_channels:,}
👥 *جروبات مرتبطة:* {total_groups:,}
📈 *نسبة النشاط:* {round((active_users/total_users)*100, 1) if total_users > 0 else 0}%
"""
        await update.message.reply_text(stats_text, parse_mode="Markdown")
    except Exception as e:
        logging.exception("خطأ في عرض الإحصائيات")
        await update.message.reply_text(f"⚠️ خطأ: {e}")


async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not all_users_data:
            await update.message.reply_text("📊 لا يوجد مستخدمين مسجلين.")
            return
        sorted_users = sorted(all_users_data.items(), key=lambda x: x[1].get("total_interactions", 0), reverse=True)[:10]
        top_text = "🏆 *أكثر 10 مستخدمين تفاعلاً*\n\n"
        for i, (user_id, udata) in enumerate(sorted_users, 1):
            username = udata.get("username", "")
            first_name = udata.get("first_name", "")
            interactions = udata.get("total_interactions", 0)
            user_display = f"@{username}" if username else (first_name[:15] if first_name else f"مستخدم {user_id}")
            top_text += f"{i}. {user_display} — 🎯 {interactions}\n"
        await update.message.reply_text(top_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ: {e}")


async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if context.args:
            search_term = context.args[0].lstrip('@')
            user_id = None
            for uid, udata in all_users_data.items():
                if udata.get("username", "").lower() == search_term.lower():
                    user_id = uid
                    break
            if not user_id and search_term.isdigit():
                user_id = int(search_term)
        else:
            user_id = update.effective_user.id

        if user_id and user_id in all_users_data:
            udata = all_users_data[user_id]
            info_text = f"""
👤 *معلومات المستخدم*

🆔 *الرقم:* `{user_id}`
👁️ *اليوزر:* @{udata.get('username', 'بدون')}
📛 *الاسم:* {udata.get('first_name', '')} {udata.get('last_name', '')}
📅 *أول ظهور:* {datetime.fromisoformat(udata.get('first_seen')).strftime('%Y-%m-%d %H:%M')}
🔄 *آخر نشاط:* {datetime.fromisoformat(udata.get('last_active')).strftime('%Y-%m-%d %H:%M')}
🎯 *عدد التفاعلات:* {udata.get('total_interactions', 0)}
"""
            await update.message.reply_text(info_text, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطأ: {e}")


# ============================= لوحة الأدمن =============================

SETTINGS_LABELS = {
    "join_btn":       "📝 نص زر المشاركة",
    "stop_btn":       "📝 النص الزر الإيقاف",
    "draw_btn":       "📝 النص الزر السحب",
    "alert_joined":   "📝 النص رسالة الانضمام",
    "winners_prefix": "📝 بادئة سطر الفائزين",
    "post_extra":     "📝 سطر إضافي في المنشور",
    "btn_home_quick":    "🏠 زر الهوم — روليت سريع",
    "btn_home_regular":  "🏠 زر الهوم — الروليت العادية",
    "btn_home_channels": "🏠 زر الهوم — القنوات",
    "btn_home_support":  "🏠 زر الهوم — الدعم",
    "btn_home_official": "🏠 زر الهوم — القناة الرسمية",
}

SCREEN_LABELS = {
    "screen_welcome":          "🏠 شاشة البداية (start)",
    "screen_quick_roulette":   "⚡ شاشة الروليت السريع",
    "screen_regular_roulette": "🎰 شاشة الروليت العادية",
    "screen_description":      "✍️ شاشة كتابة النص",
    "screen_req_channels":     "🔒 شاشة القنوات الشرطية",
    "screen_winners_count":    "🎯 شاشة عدد الفائزين",
    "screen_support":          "💬 شاشة الدعم",
}

CHANNEL_TEXT_LABELS = {
    "ct_qr_open_header":  "📢 عنوان الروليت السريع (مفتوح)",
    "ct_qr_open_body":    "📢 نص الروليت السريع (مفتوح)",
    "ct_qr_full_header":  "📢 عنوان الروليت السريع (مكتمل)",
    "ct_qr_winner_fast":  "📢 نص إعلان الفائز السريع",
    "ct_qr_winner_slow":  "📢 نص إعلان الفائز البطيء",
    "ct_roulette_winner": "📢 نص إعلان فائزي الروليت العادية",
}

USERS_PER_PAGE = 20


def _admin_home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إحصائيات المستخدمين", callback_data="adm_u")],
        [InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="adm_ul_0")],
        [InlineKeyboardButton("⚙️ إعدادات الأزرار والنصوص", callback_data="adm_s")],
        [InlineKeyboardButton("📢 نصوص القناة", callback_data="adm_ct")],
        [InlineKeyboardButton("📺 تعديل الشاشات", callback_data="adm_screens")],
        [InlineKeyboardButton("➕ أزرار مخصصة في الهوم", callback_data="adm_custom")],
        [InlineKeyboardButton("💬 استبدال النصوص", callback_data="adm_r")],
        [InlineKeyboardButton("👮 إدارة الأدمنية", callback_data="adm_admins")],
    ])


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_bot_admin(user):
        await update.message.reply_text("❌ ليس لديك صلاحية.")
        return
    await update.message.reply_text(
        "👑 <b>لوحة الأدمن</b>\n\nاختر من القائمة:",
        parse_mode="HTML",
        reply_markup=_admin_home_kb()
    )


async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_settings
    q = update.callback_query
    user = q.from_user
    if not is_bot_admin(user):
        await q.answer("❌ ليس لديك صلاحية.", show_alert=True)
        return
    await q.answer()
    data = q.data

    if data == "admin_home":
        await q.edit_message_text(
            "👑 <b>لوحة الأدمن</b>\n\nاختر من القائمة:",
            parse_mode="HTML",
            reply_markup=_admin_home_kb()
        )

    elif data == "adm_u":
        total = len(all_users_data)
        week_ago = datetime.now().timestamp() - 7 * 24 * 3600
        active = sum(
            1 for u in all_users_data.values()
            if datetime.fromisoformat(u.get("last_active", datetime.now().isoformat())).timestamp() > week_ago
        )
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_new = sum(1 for fs in user_first_seen.values() if fs >= today_start)
        text = (
            f"👥 <b>إحصائيات المستخدمين</b>\n\n"
            f"📊 الإجمالي: <b>{total:,}</b>\n"
            f"🟢 نشطون (7 أيام): <b>{active:,}</b>\n"
            f"🆕 انضموا اليوم: <b>{today_new:,}</b>"
        )
        await q.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")]])
        )

    elif data.startswith("adm_ul_"):
        page = int(data.split("_")[-1])
        users_list = list(all_users_data.items())
        total = len(users_list)
        start = page * USERS_PER_PAGE
        end = start + USERS_PER_PAGE
        chunk = users_list[start:end]

        lines = [f"📋 <b>قائمة المستخدمين</b> ({start + 1}–{min(end, total)} من {total})\n"]
        for uid, u in chunk:
            uname = f"@{u['username']}" if u.get("username") else "—"
            fname = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or "—"
            lines.append(f"🆔 <code>{uid}</code> | {uname} | {fname}")

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"adm_ul_{page - 1}"))
        if end < total:
            nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"adm_ul_{page + 1}"))
        btns = []
        if nav:
            btns.append(nav)
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])

        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_s":
        s = load_settings()
        lines = ["⚙️ <b>إعدادات البوت</b>\n"]
        for key, label in SETTINGS_LABELS.items():
            val = s.get(key, "") or "—"
            lines.append(f"{label}:\n<code>{val}</code>\n")
        btns = [[InlineKeyboardButton(label, callback_data=f"adm_e_{key}")]
                for key, label in SETTINGS_LABELS.items()]
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data.startswith("adm_e_"):
        key = data[6:]
        s = load_settings()
        current = s.get(key, "") or "—"
        is_screen = key in SCREEN_LABELS
        is_ct = key in CHANNEL_TEXT_LABELS
        label = SCREEN_LABELS.get(key) or CHANNEL_TEXT_LABELS.get(key) or SETTINGS_LABELS.get(key, key)
        back = "adm_screens" if is_screen else ("adm_ct" if is_ct else "adm_s")
        context.user_data["adm_editing"] = key
        hint = "\n\n💡 يمكنك استخدام {first_name} و {uid} كمتغيرات" if key == "screen_welcome" else ""
        # إضافة متغيرات مسموح بها لنصوص القناة
        ct_hints = {
            "ct_qr_open_header": "\n\n💡 يمكنك استخدام {N} لعدد المقاعد",
            "ct_qr_open_body":   "\n\n💡 نص يظهر أسفل العنوان في بوست الروليت المفتوح",
            "ct_qr_full_header": "\n\n💡 يمكنك استخدام {N} لعدد المقاعد",
            "ct_qr_winner_fast": "\n\n💡 يمكنك استخدام {name} لاسم الفائز",
            "ct_qr_winner_slow": "\n\n💡 يمكنك استخدام {name} لاسم الفائز",
            "ct_roulette_winner": "\n\n💡 نص العنوان قبل قائمة الفائزين في الروليت العادية",
        }
        if is_ct:
            hint = ct_hints.get(key, "")
        await q.edit_message_text(
            f"✏️ <b>تعديل: {label}</b>\n\n"
            f"النص الحالي:\n<code>{current}</code>\n\n"
            f"أرسل النص الجديد:{hint}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data=back)]])
        )

    elif data == "adm_ct":
        s = load_settings()
        lines = ["📢 <b>نصوص القناة</b>\n\nكل نص بيظهر في القناة تقدر تعدله من هنا:\n"]
        for key, label in CHANNEL_TEXT_LABELS.items():
            val = s.get(key, "") or "<i>افتراضي</i>"
            preview = val[:60] + ("..." if len(val) > 60 else "")
            lines.append(f"<b>{label}</b>\n{preview}\n")
        btns = [[InlineKeyboardButton(label, callback_data=f"adm_e_{key}")]
                for key, label in CHANNEL_TEXT_LABELS.items()]
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_screens":
        s = load_settings()
        lines = ["📺 <b>تعديل الشاشات</b>\n\nاختر الشاشة اللي تريد تعديل نصها:"]
        btns = [[InlineKeyboardButton(label, callback_data=f"adm_e_{key}")]
                for key, label in SCREEN_LABELS.items()]
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_custom" or data == "adm_custom_refresh":
        s = load_settings()
        custom = s.get("custom_home_btns", [])
        lines = ["➕ <b>الأزرار المخصصة في الهوم</b>\n"]
        if custom:
            for i, btn in enumerate(custom):
                if btn.get("url"):
                    lines.append(f"{i + 1}. <b>{btn['text']}</b>\n🔗 {btn['url']}\n")
                else:
                    msg_preview = (btn.get("msg", "") or "")[:50]
                    lines.append(f"{i + 1}. <b>{btn['text']}</b>\n💬 {msg_preview}{'...' if len(btn.get('msg',''))>50 else ''}\n")
        else:
            lines.append("لا توجد أزرار مضافة بعد.")
        btns = []
        for i, btn in enumerate(custom):
            btns.append([InlineKeyboardButton(f"🗑️ حذف: {btn['text']}", callback_data=f"adm_del_custom_{i}")])
        btns.append([InlineKeyboardButton("➕ إضافة زر جديد", callback_data="adm_add_custom")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_add_custom":
        await q.edit_message_text(
            "➕ <b>إضافة زر مخصص</b>\n\nاختر نوع الزر:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 رابط URL", callback_data="adm_add_custom_url")],
                [InlineKeyboardButton("💬 رسالة نصية", callback_data="adm_add_custom_msg")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]
            ])
        )

    elif data == "adm_add_custom_url":
        context.user_data["adm_custom_step"] = "text"
        context.user_data["adm_custom_type"] = "url"
        await q.edit_message_text(
            "➕ <b>زر رابط</b>\n\nأرسل <b>نص الزر</b> الذي سيظهر للمستخدم:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]])
        )

    elif data == "adm_add_custom_msg":
        context.user_data["adm_custom_step"] = "text"
        context.user_data["adm_custom_type"] = "msg"
        await q.edit_message_text(
            "➕ <b>زر رسالة</b>\n\nأرسل <b>نص الزر</b> الذي سيظهر للمستخدم:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]])
        )

    elif data.startswith("adm_del_custom_"):
        idx = int(data.split("_")[-1])
        s = load_settings()
        custom = s.get("custom_home_btns", [])
        if 0 <= idx < len(custom):
            removed = custom.pop(idx)
            s["custom_home_btns"] = custom
            save_settings(s)
            bot_settings = s
            await q.answer(f"✅ تم حذف زر «{removed['text']}»", show_alert=True)
        # أعِد عرض القائمة
        custom = s.get("custom_home_btns", [])
        lines = ["➕ <b>الأزرار المخصصة في الهوم</b>\n"]
        if custom:
            for i, btn in enumerate(custom):
                if btn.get("url"):
                    lines.append(f"{i + 1}. <b>{btn['text']}</b>\n🔗 {btn['url']}\n")
                else:
                    msg_preview = (btn.get("msg", "") or "")[:50]
                    lines.append(f"{i + 1}. <b>{btn['text']}</b>\n💬 {msg_preview}{'...' if len(btn.get('msg',''))>50 else ''}\n")
        else:
            lines.append("لا توجد أزرار مضافة بعد.")
        btns = []
        for i, btn in enumerate(custom):
            btns.append([InlineKeyboardButton(f"🗑️ حذف: {btn['text']}", callback_data=f"adm_del_custom_{i}")])
        btns.append([InlineKeyboardButton("➕ إضافة زر جديد", callback_data="adm_add_custom")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_r":
        s = load_settings()
        reps = s.get("replacements", {})
        lines = ["💬 <b>استبدال النصوص</b>\n"]
        if reps:
            for old, new in reps.items():
                lines.append(f"🔄 <code>{old}</code>\n    ↓\n<code>{new}</code>\n")
        else:
            lines.append("لا توجد استبدالات مضافة بعد.")
        btns = []
        for old in reps:
            safe = old[:25]
            btns.append([InlineKeyboardButton(f"🗑️ حذف: {safe}", callback_data=f"adm_rd_{old}")])
        btns.append([InlineKeyboardButton("➕ إضافة استبدال", callback_data="adm_ra")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_ra":
        context.user_data["adm_replace_step"] = "key"
        await q.edit_message_text(
            "💬 <b>إضافة استبدال</b>\n\nأرسل الكلام الأصلي اللي تريد استبداله:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_r")]])
        )

    elif data.startswith("adm_rd_"):
        old_key = data[7:]
        s = load_settings()
        s.setdefault("replacements", {}).pop(old_key, None)
        save_settings(s)
        bot_settings = s
        await q.edit_message_text(
            f"✅ تم حذف الاستبدال: <code>{old_key}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الاستبدالات", callback_data="adm_r")]])
        )

    elif data == "adm_admins":
        s = load_settings()
        admins = s.get("extra_admins", [])
        lines = ["👮 <b>إدارة الأدمنية</b>\n"]
        if admins:
            for aid in admins:
                u = all_users_data.get(aid, {})
                uname = f"@{u['username']}" if u.get("username") else "—"
                lines.append(f"🆔 <code>{aid}</code> {uname}")
        else:
            lines.append("لا يوجد أدمنية مضافون.")
        btns = []
        for aid in admins:
            btns.append([InlineKeyboardButton(f"🗑️ حذف {aid}", callback_data=f"adm_da_{aid}")])
        btns.append([InlineKeyboardButton("➕ إضافة أدمن (بالـ ID)", callback_data="adm_aa")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_home")])
        await q.edit_message_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "adm_aa":
        context.user_data["adm_adding_admin"] = True
        await q.edit_message_text(
            "👮 أرسل الـ user_id للأدمن الجديد (رقم فقط):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_admins")]])
        )

    elif data.startswith("adm_da_"):
        aid = int(data[7:])
        s = load_settings()
        admins = s.get("extra_admins", [])
        if aid in admins:
            admins.remove(aid)
        s["extra_admins"] = admins
        save_settings(s)
        bot_settings = s
        await q.edit_message_text(
            f"✅ تم حذف الأدمن <code>{aid}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الأدمنية", callback_data="adm_admins")]])
        )


async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """يعالج رسائل الأدمن أثناء التعديل — يرجع True لو تم التعامل معها"""
    user = update.effective_user
    if not is_bot_admin(user):
        return False
    text = update.message.text.strip()

    if "adm_editing" in context.user_data:
        key = context.user_data.pop("adm_editing")
        s = load_settings()
        # للشاشات: احفظ النص مع تنسيق HTML (عريض، مائل...) محفوظ
        if key in SCREEN_LABELS or key in CHANNEL_TEXT_LABELS:
            save_text = update.message.text_html
        else:
            save_text = text
        s[key] = save_text
        save_settings(s)
        global bot_settings
        bot_settings = s
        if key in SCREEN_LABELS:
            label = SCREEN_LABELS[key]
            back_data = "adm_screens"
            back_label = "🔙 الشاشات"
        elif key in CHANNEL_TEXT_LABELS:
            label = CHANNEL_TEXT_LABELS[key]
            back_data = "adm_ct"
            back_label = "🔙 نصوص القناة"
        else:
            label = SETTINGS_LABELS.get(key, key)
            back_data = "adm_s"
            back_label = "🔙 الإعدادات"
        await update.message.reply_text(
            f"✅ تم تحديث {label}\n\nتم الحفظ بالتنسيق كما كتبته.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data=back_data)]])
        )
        return True

    if context.user_data.get("adm_replace_step") == "key":
        context.user_data["adm_replace_key"] = text
        context.user_data["adm_replace_step"] = "value"
        await update.message.reply_text(
            f"💬 الكلام الأصلي: <code>{text}</code>\n\nالآن أرسل الكلام الجديد اللي هيحل محله:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_r")]])
        )
        return True

    if context.user_data.get("adm_replace_step") == "value":
        old_key = context.user_data.pop("adm_replace_key", "")
        context.user_data.pop("adm_replace_step")
        s = load_settings()
        s.setdefault("replacements", {})[old_key] = text
        save_settings(s)
        bot_settings = s
        await update.message.reply_text(
            f"✅ تم إضافة الاستبدال:\n<code>{old_key}</code>\n↓\n<code>{text}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الاستبدالات", callback_data="adm_r")]])
        )
        return True

    if context.user_data.get("adm_adding_admin"):
        context.user_data.pop("adm_adding_admin")
        if text.isdigit():
            new_aid = int(text)
            s = load_settings()
            admins = s.get("extra_admins", [])
            if new_aid not in admins:
                admins.append(new_aid)
            s["extra_admins"] = admins
            save_settings(s)
            bot_settings = s
            await update.message.reply_text(
                f"✅ تم إضافة الأدمن: <code>{new_aid}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الأدمنية", callback_data="adm_admins")]])
            )
        else:
            await update.message.reply_text("❌ أرسل رقم (user_id) صحيح فقط.")
        return True

    if context.user_data.get("adm_custom_step") == "text":
        context.user_data["adm_custom_text"] = text
        btn_type = context.user_data.get("adm_custom_type", "url")
        if btn_type == "msg":
            context.user_data["adm_custom_step"] = "msg"
            await update.message.reply_text(
                f"💬 نص الزر: <b>{text}</b>\n\nالآن أرسل <b>محتوى الرسالة</b> اللي ستظهر للمستخدم لما يضغط الزر:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]])
            )
        else:
            context.user_data["adm_custom_step"] = "url"
            await update.message.reply_text(
                f"🔗 نص الزر: <b>{text}</b>\n\nالآن أرسل <b>الرابط (URL)</b> اللي سيفتحه الزر:\n"
                f"<i>مثال: https://t.me/mychannel</i>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]])
            )
        return True

    if context.user_data.get("adm_custom_step") == "msg":
        btn_text = context.user_data.pop("adm_custom_text", "")
        context.user_data.pop("adm_custom_step", None)
        context.user_data.pop("adm_custom_type", None)
        s = load_settings()
        custom = s.get("custom_home_btns", [])
        custom.append({"text": btn_text, "msg": text})
        s["custom_home_btns"] = custom
        save_settings(s)
        bot_settings = s
        await update.message.reply_text(
            f"✅ تم إضافة الزر بنجاح!\n\n"
            f"📝 الزر: <b>{btn_text}</b>\n"
            f"💬 الرسالة: {text[:80]}{'...' if len(text) > 80 else ''}\n\n"
            f"سيظهر الزر في الشاشة الرئيسية فوراً.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الأزرار المخصصة", callback_data="adm_custom")]])
        )
        return True

    if context.user_data.get("adm_custom_step") == "url":
        btn_text = context.user_data.pop("adm_custom_text", "")
        context.user_data.pop("adm_custom_step", None)
        context.user_data.pop("adm_custom_type", None)
        if not text.startswith("http"):
            await update.message.reply_text(
                "❌ الرابط يجب أن يبدأ بـ http أو https. حاول مجدداً:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="adm_custom")]])
            )
            context.user_data["adm_custom_step"] = "url"
            context.user_data["adm_custom_text"] = btn_text
            context.user_data["adm_custom_type"] = "url"
            return True
        s = load_settings()
        custom = s.get("custom_home_btns", [])
        custom.append({"text": btn_text, "url": text})
        s["custom_home_btns"] = custom
        save_settings(s)
        bot_settings = s
        await update.message.reply_text(
            f"✅ تم إضافة الزر بنجاح!\n\n"
            f"📝 النص: <b>{btn_text}</b>\n"
            f"🔗 الرابط: {text}\n\n"
            f"سيظهر الزر في الشاشة الرئيسية فوراً.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الأزرار المخصصة", callback_data="adm_custom")]])
        )
        return True

    return False


# =========== تدوير الروليت السريع ===========
async def qr_fast_spin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    gid = q.data.split("_", 2)[2]
    cr = completed_roulettes.get(gid)

    if not cr or not cr.get("quick_roulette"):
        await q.answer("❌ الروليت غير موجود أو منتهي الصلاحية.", show_alert=True)
        return
    if q.from_user.id != cr["owner_id"]:
        await q.answer("❌ فقط صاحب الروليت يمكنه التدوير.", show_alert=True)
        return

    participants = cr["valid_participants"]
    if not participants:
        await q.answer("❌ لا يوجد مشاركون.", show_alert=True)
        return

    winner_id = random.choice(participants)
    w_data = cr["participants_data"].get(winner_id, {})
    fn = w_data.get("first_name", "مستخدم")
    ln = w_data.get("last_name", "") or ""
    full = f"{fn} {ln}".strip()

    winner_header = bot_settings.get("ct_qr_winner_fast") or "🎉 انتهى التدوير السريع!\n\n🏆 الفائز هو:"
    winner_header = winner_header.replace("{name}", full)
    result_text = (
        f"<b>{winner_header}</b>\n"
        f'<a href="tg://user?id={winner_id}">{full}</a>\n\n'
        f'<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n'
        f'<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>'
    )

    try:
        await context.bot.edit_message_text(
            chat_id=cr["chat_id"],
            message_id=cr["result_msg_id"],
            text=result_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.warning(f"فشل تحديث رسالة التدوير السريع: {e}")

    del completed_roulettes[gid]
    await q.answer("⚡ تم اختيار الفائز!")


async def qr_slow_spin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    gid = q.data.split("_", 2)[2]
    cr = completed_roulettes.get(gid)

    if not cr or not cr.get("quick_roulette"):
        await q.answer("❌ الروليت غير موجود أو منتهي الصلاحية.", show_alert=True)
        return
    if q.from_user.id != cr["owner_id"]:
        await q.answer("❌ فقط صاحب الروليت يمكنه التدوير.", show_alert=True)
        return

    participants = list(cr["valid_participants"])
    if not participants:
        await q.answer("❌ لا يوجد مشاركون.", show_alert=True)
        return

    await q.answer("🐢 بدأ التدوير البطيء...")
    del completed_roulettes[gid]

    chat_id = cr["chat_id"]
    msg_id = cr["result_msg_id"]
    pdata = cr["participants_data"]
    max_p = cr.get("max_participants", len(participants))

    remaining = list(participants)
    random.shuffle(remaining)

    asyncio.create_task(_run_slow_spin(context.bot, chat_id, msg_id, remaining, pdata, max_p))


async def _run_slow_spin(bot, chat_id, msg_id, remaining, pdata, max_p):
    while len(remaining) > 1:
        eliminated = remaining.pop(0)
        e_data = pdata.get(eliminated, {})
        e_fn = e_data.get("first_name", "مستخدم")
        e_ln = e_data.get("last_name", "") or ""
        e_full = f"{e_fn} {e_ln}".strip()

        lines = [f"🎰 <b>التدوير البطيء ({len(remaining)}/{max_p})</b>\n"]
        for i, pid in enumerate(remaining, 1):
            d = pdata.get(pid, {})
            fn = d.get("first_name", "مستخدم")
            ln = d.get("last_name", "") or ""
            lines.append(f'{i}. <a href="tg://user?id={pid}">{fn} {ln}'.rstrip() + "</a>")
        lines.append(f'\n❌ خرج: <a href="tg://user?id={eliminated}">{e_full}</a>')
        lines.append(f'\n<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>')

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text="\n".join(lines),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception:
            pass
        await asyncio.sleep(2)

    # آخر شخص = الفائز
    winner_id = remaining[0]
    w_data = pdata.get(winner_id, {})
    fn = w_data.get("first_name", "مستخدم")
    ln = w_data.get("last_name", "") or ""
    full = f"{fn} {ln}".strip()

    winner_header = bot_settings.get("ct_qr_winner_slow") or "🎉 انتهى التدوير البطيء!\n\n🏆 الفائز الأخير هو:"
    winner_header = winner_header.replace("{name}", full)
    result_text = (
        f"<b>{winner_header}</b>\n"
        f'<a href="tg://user?id={winner_id}">{full}</a>\n\n'
        f'<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n'
        f'<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>'
    )
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=result_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logging.warning(f"فشل تحديث رسالة التدوير البطيء: {e}")


# =========== أزرار الهوم النصية ===========
async def custom_btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        idx = int(q.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return
    s = load_settings()
    custom = s.get("custom_home_btns", [])
    if idx < 0 or idx >= len(custom):
        await q.answer("❌ الزر غير موجود.", show_alert=True)
        return
    btn = custom[idx]
    msg_text = btn.get("msg", "")
    if not msg_text:
        return
    await context.bot.send_message(
        q.message.chat.id,
        msg_text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# =========== نظام إعادة السحب ===========
async def redraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    giveaway_id = q.data.split("_", 1)[1]
    cr = completed_roulettes.get(giveaway_id)

    if not cr:
        await q.answer("❌ انتهت صلاحية هذا السحب.", show_alert=True)
        return
    if q.from_user.id != cr["owner_id"]:
        await q.answer("❌ فقط صاحب الروليت يمكنه استخدام هذا الخيار.", show_alert=True)
        return

    winners_count = cr["winners_count"]
    await q.answer("📨 تم إرسال رسالة في البوت، أرسل الأرقام", show_alert=True)

    context.user_data["awaiting_redraw"] = giveaway_id

    await context.bot.send_message(
        cr["owner_id"],
        f"🔄 <b>اسحب فائز آخر</b>\n\n"
        f"أرسل أرقام مراكز الفائزين الذين تريد تغييرهم\n"
        f"مثال: <code>1</code>  أو  <code>1 3</code>  أو  <code>1,3,5</code>\n\n"
        f"💡 يمكنك إدخال أي رقم حتى لو كان خارج عدد الفائزين الأصلي لإضافة فائزين جدد",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="redraw_cancel")]])
    )


async def redraw_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.pop("awaiting_redraw", None)
    await q.edit_message_text("❌ تم إلغاء إعادة السحب.")


async def handle_redraw_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """يعالج رسالة أرقام الفائزين لإعادة السحب — يرجع True لو تم التعامل معها"""
    uid = update.effective_user.id
    giveaway_id = context.user_data.get("awaiting_redraw")
    if not giveaway_id:
        return False

    cr = completed_roulettes.get(giveaway_id)
    if not cr or uid != cr["owner_id"]:
        return False

    text = update.message.text.strip()
    # تحليل الأرقام: مفصولة بمسافة أو فاصلة أو سطر جديد
    nums_raw = re.split(r"[\s,،\n]+", text)
    try:
        positions = list(set(int(n) for n in nums_raw if n.strip().isdigit()))
    except ValueError:
        await update.message.reply_text("❌ أرسل أرقاماً صحيحة فقط مثل: 1 3 أو 1,3")
        return True

    if not positions:
        await update.message.reply_text("❌ لم يتم إدخال أي رقم.")
        return True

    invalid_zeros = [p for p in positions if p < 1]
    if invalid_zeros:
        await update.message.reply_text("❌ الأرقام يجب أن تكون 1 أو أكبر.")
        return True

    # الفائزون الحاليون
    current_winners = list(cr["winners"])
    # المشاركون المحجوزون = الفائزون الحاليون الذين لن يُغيَّروا
    kept_winner_ids = set(
        current_winners[i - 1] for i in range(1, len(current_winners) + 1)
        if i not in positions
    )
    # المشاركون المؤهلون = الكل ناقص المحجوزين
    pool = [p for p in cr["valid_participants"] if p not in kept_winner_ids]

    if len(pool) < len(positions):
        await update.message.reply_text(
            f"⚠️ لا يوجد مشاركون كافون للسحب ({len(pool)} متبقي، تحتاج {len(positions)})."
        )
        return True

    new_picks = random.sample(pool, len(positions))

    # تحديث قائمة الفائزين
    for i, pos in enumerate(sorted(positions)):
        if (pos - 1) < len(current_winners):
            current_winners[pos - 1] = new_picks[i]
        else:
            current_winners.append(new_picks[i])

    cr["winners"] = current_winners
    context.user_data.pop("awaiting_redraw", None)

    # بناء نص الفائزين الجديد
    _rw_header2 = bot_settings.get("ct_roulette_winner") or "🎉 تم انتهاء السحب وتم اختيار الفائزين:"
    new_text = f"<b>{_rw_header2}</b>\n\n"
    for i, winner_id in enumerate(current_winners, 1):
        w_data = cr["participants_data"].get(winner_id, {})
        fn = w_data.get("first_name", "مستخدم")
        ln = w_data.get("last_name", "") or ""
        full = f"{fn} {ln}".strip()
        new_text += f'{i}. <a href="tg://user?id={winner_id}">{full}</a>\n'

    new_text += f'\n<blockquote><a href="{BOT_PUBLIC_LINK}">Crypto Royale</a>\n<a href="https://t.me/CryptoRoyale10">سحوبات Crypto Royale</a></blockquote>'

    # تعديل رسالة النتائج في القناة
    try:
        await context.bot.edit_message_text(
            chat_id=cr["chat_id"],
            message_id=cr["result_msg_id"],
            text=new_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 اسحب فائز آخر", callback_data=f"redraw_{giveaway_id}")]
            ])
        )
    except Exception as e:
        logging.warning(f"⚠️ فشل تعديل رسالة النتائج: {e}")

    await update.message.reply_text(
        f"✅ <b>تم تحديث الفائزين بنجاح!</b>\n\n{new_text}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    return True


# =========== نظام الإبلاغ ===========
async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_settings
    q = update.callback_query
    reporter_id = q.from_user.id
    reported_uid = int(q.data.split("_", 1)[1])

    # لا يُبلَّغ على نفسك
    if reporter_id == reported_uid:
        await q.answer("❌ لا يمكنك الإبلاغ عن نفسك.", show_alert=True)
        return

    await q.answer("✅ تم إرسال الإبلاغ بنجاح", show_alert=True)

    s = load_settings()
    reports = s.get("user_reports", {})
    key = str(reported_uid)
    reports[key] = reports.get(key, 0) + 1
    s["user_reports"] = reports

    count = reports[key]
    pct = min(int(count / MAX_REPORTS * 100), 100)

    # حجب تلقائي عند 100%
    banned = s.get("banned_users", [])
    newly_banned = False
    if pct >= 100 and reported_uid not in banned:
        banned.append(reported_uid)
        s["banned_users"] = banned
        newly_banned = True

    save_settings(s)
    bot_settings = s

    # جلب بيانات المُبلَّغ عنه
    rep_data = all_users_data.get(reported_uid, {})
    rep_name = f"{rep_data.get('first_name', '')} {rep_data.get('last_name', '')}".strip() or "مجهول"
    rep_username = f"@{rep_data['username']}" if rep_data.get("username") else "—"

    # إشعار المالك
    owner_id = next(
        (int(uid) for uid, u in all_users_data.items() if u.get("username") == OWNER_USERNAME),
        None
    )
    notif_text = (
        f"🚨 <b>إبلاغ جديد</b>\n\n"
        f"الاسم: <b>{rep_name}</b>\n"
        f"user: {rep_username}\n"
        f"id: <code>{reported_uid}</code>\n\n"
        f"📊 نسبة الإبلاغات: <b>{pct}%</b>"
    )
    if newly_banned:
        notif_text += "\n\n🚫 <b>تم حجب هذا المستخدم تلقائياً (100%)</b>"

        # إشعار المحجوب نفسه
        try:
            await context.bot.send_message(
                reported_uid,
                "⚠️ <b>تحذير</b>\n\nتلقيت عدداً كافياً من الإبلاغات وتم <b>حظرك</b> من إنشاء سحوبات جديدة.\n"
                f"للتواصل: @{OWNER_USERNAME}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    if owner_id:
        try:
            await context.bot.send_message(owner_id, notif_text, parse_mode="HTML")
        except Exception:
            pass


# =========== استخراج ID الإيموجي المخصص ===========
async def getemoji_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /getemoji — رد على رسالة تحتوي custom emoji ليعطيك الـ ID.
    يدعم:
      - إيموجي مخصص مدمج في نص (MessageEntity)
      - إيموجي مخصص مرسل كقطعة منفردة (Sticker)
    """
    msg = update.effective_message

    if not msg.reply_to_message:
        await msg.reply_text(
            "↩️ <b>كيفية الاستخدام:</b>\n\n"
            "1️⃣ أرسل أو أعد توجيه رسالة تحتوي إيموجي مخصص (animated premium emoji)\n"
            "2️⃣ <b>ارد</b> على تلك الرسالة بـ /getemoji\n\n"
            "💡 يعمل مع الإيموجي المدمج في النص وكذلك الإيموجي المرسل كقطعة منفردة.",
            parse_mode="HTML"
        )
        return

    replied = msg.reply_to_message
    custom_ids = []

    # 1) إيموجي في entities النص أو التعليق
    all_ents = list(replied.entities or []) + list(replied.caption_entities or [])
    for ent in all_ents:
        if ent.type == MessageEntity.CUSTOM_EMOJI and ent.custom_emoji_id:
            if ent.custom_emoji_id not in custom_ids:
                custom_ids.append(ent.custom_emoji_id)

    # 2) إيموجي مرسل كـ sticker منفرد (custom emoji sticker)
    if replied.sticker and replied.sticker.custom_emoji_id:
        eid = replied.sticker.custom_emoji_id
        if eid not in custom_ids:
            custom_ids.append(eid)

    # 3) رسالة تحتوي أكثر من sticker (نادر لكن ممكن)
    if replied.document and getattr(replied.document, "custom_emoji_id", None):
        eid = replied.document.custom_emoji_id
        if eid not in custom_ids:
            custom_ids.append(eid)

    logging.info(
        f"[getemoji] replied msg_id={replied.message_id} "
        f"has_sticker={bool(replied.sticker)} "
        f"entities={[e.type for e in (replied.entities or [])]} "
        f"found_ids={custom_ids}"
    )

    if not custom_ids:
        # تشخيص تفصيلي لمساعدة المستخدم
        diag = []
        if replied.sticker:
            s = replied.sticker
            diag.append(f"• النوع: Sticker")
            diag.append(f"• is_video: {s.is_video}")
            diag.append(f"• is_animated: {s.is_animated}")
            diag.append(f"• custom_emoji_id: {s.custom_emoji_id or 'غير موجود'}")
            diag.append(f"• set_name: {s.set_name or 'غير موجود'}")
        elif replied.text:
            diag.append(f"• النوع: رسالة نصية")
            diag.append(f"• عدد entities: {len(replied.entities or [])}")
            for e in (replied.entities or []):
                diag.append(f"  - {e.type}")
        else:
            diag.append(f"• النوع: {replied.effective_attachment.__class__.__name__ if replied.effective_attachment else 'غير معروف'}")

        await msg.reply_text(
            "❌ <b>لم يتم العثور على custom emoji ID.</b>\n\n"
            "<b>تشخيص الرسالة:</b>\n" + "\n".join(diag) + "\n\n"
            "💡 <b>فرق مهم:</b>\n"
            "• Custom emoji = إيموجي Premium متحرك يُرسل داخل نص\n"
            "• Sticker عادي = لا يحتوي custom_emoji_id\n"
            "• Sticker Custom Emoji = له custom_emoji_id ✓",
            parse_mode="HTML"
        )
        return

    lines = ["✅ <b>Custom Emoji IDs المستخرجة:</b>\n"]
    for i, eid in enumerate(custom_ids, 1):
        lines.append(f"{i}. <code>{eid}</code>")
    lines.append(
        f"\n💡 استخدمه في رسائل البوت هكذا:\n"
        f"<code>[emoji:{custom_ids[0]}]</code>"
    )

    await msg.reply_text("\n".join(lines), parse_mode="HTML")


# =========== تشغيل البوت ===========
def main():
    load_data()
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # أوامر
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("count", عدد_المستخدمين))
    app.add_handler(CommandHandler("stats", عدد_المستخدمين))
    app.add_handler(CommandHandler("topusers", show_top_users))
    app.add_handler(CommandHandler("userinfo", user_info))
    app.add_handler(CommandHandler("users", users_count_cmd))
    app.add_handler(CommandHandler("draw_winner", draw_winner_cmd))
    app.add_handler(CommandHandler("repost_giveaway", repost_giveaway_cmd))
    app.add_handler(CommandHandler("schedule_repost", schedule_repost_cmd))
    app.add_handler(CommandHandler("getemoji", getemoji_cmd))

    # أدمن
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^(admin_home|adm_.*)$"))
    app.add_handler(CallbackQueryHandler(report_handler, pattern=r"^report_\d+$"))
    app.add_handler(CallbackQueryHandler(custom_btn_handler, pattern=r"^custombtn_\d+$"))
    app.add_handler(CallbackQueryHandler(qr_fast_spin_handler, pattern=r"^qrspin_fast_.+$"))
    app.add_handler(CallbackQueryHandler(qr_slow_spin_handler, pattern=r"^qrspin_slow_.+$"))
    app.add_handler(CallbackQueryHandler(redraw_handler, pattern=r"^redraw_(?!cancel).+$"))
    app.add_handler(CallbackQueryHandler(redraw_cancel_handler, pattern="^redraw_cancel$"))

    # أزرار القائمة الرئيسية
    app.add_handler(CallbackQueryHandler(go_home, pattern="^go_home$"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^support$"))
    app.add_handler(CallbackQueryHandler(channels_menu, pattern="^channels_menu$"))
    app.add_handler(CallbackQueryHandler(link_channel_prompt, pattern="^link_channel$"))
    app.add_handler(CallbackQueryHandler(link_group_prompt, pattern="^link_group$"))
    app.add_handler(CallbackQueryHandler(unlink_menu, pattern="^unlink_menu$"))
    app.add_handler(CallbackQueryHandler(do_unlink, pattern="^unlink_(ch|gr)_\\d+$"))

    # روليت سريع
    app.add_handler(CallbackQueryHandler(quick_roulette_start, pattern="^quick_roulette$"))
    app.add_handler(CallbackQueryHandler(quick_roulette_select_chat, pattern="^qr_sel_-?\\d+$"))
    app.add_handler(CallbackQueryHandler(quick_roulette_select_count, pattern="^qr_cnt_\\d+$"))

    # روليت عادية
    app.add_handler(CallbackQueryHandler(create_roulette, pattern="^create_regular$"))
    app.add_handler(CallbackQueryHandler(regular_roulette_select_chat, pattern="^rr_sel_-?\\d+$"))
    app.add_handler(CallbackQueryHandler(republish_roulette, pattern="^republish_roulette$"))
    app.add_handler(CallbackQueryHandler(handle_description_buttons, pattern="^(add_req_channel|skip_req_channel|back_to_description|add_more_channels|finish_channels)$"))

    # أزرار الروليت النشطة
    app.add_handler(CallbackQueryHandler(handle_roulette_buttons))

    # رسائل نصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    logging.info(f"✅ البوت يعمل الآن مع {len(all_users_data)} مستخدم مسجل...")

    async def on_startup(app):
        try:
            await app.bot.set_my_short_description(short_description="")
        except Exception:
            pass

    app.post_init = on_startup

    is_deployed = os.environ.get("REPLIT_DEPLOYMENT") == "1"

    if is_deployed:
        port = int(os.environ.get("PORT", 8080))
        domains_raw = os.environ.get("REPLIT_DOMAINS", "")
        logging.info(f"[DEPLOY] PORT={port} | REPLIT_DOMAINS='{domains_raw}'")
        domain = domains_raw.split(",")[0].strip() if domains_raw else ""
        if domain:
            webhook_url = f"https://{domain}/tgwebhook"
            logging.info(f"[DEPLOY] Webhook → {webhook_url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path="/tgwebhook",
                webhook_url=webhook_url,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True,
            )
        else:
            logging.error("[DEPLOY] REPLIT_DOMAINS فارغ! سيعمل بـ polling احتياطياً.")
            app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)
    else:
        # وضع التطوير — تحقق أولاً إذا كان webhook المنشور نشطاً (بدون asyncio)
        import urllib.request as _urlreq, json as _json

        def _check_webhook_sync():
            try:
                url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
                with _urlreq.urlopen(url, timeout=5) as resp:
                    data = _json.loads(resp.read())
                    return data.get("result", {}).get("url", "")
            except Exception as e:
                logging.warning(f"[DEV] فشل فحص الـ webhook: {e}")
                return ""

        active_webhook = _check_webhook_sync()

        if active_webhook:
            import http.server
            import socketserver
            logging.info(f"[DEV] webhook مفعّل ({active_webhook}) — لن يعمل polling لتجنب التعارض")
            logging.info("[DEV] يشتغل خادم صحي فقط على المنفذ 8080")

            class _HealthHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Bot running via deployed webhook")
                def log_message(self, fmt, *args):
                    pass

            with socketserver.TCPServer(("0.0.0.0", 8080), _HealthHandler) as httpd:
                httpd.serve_forever()
        else:
            logging.info("🔄 وضع التطوير — Polling (لا يوجد webhook نشط)")
            app.run_polling(allowed_updates=["message", "callback_query"], drop_pending_updates=True)


if __name__ == "__main__":
    main()
