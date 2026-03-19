import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- FONCTIONS API PMU (Source fiable pour le programme) ---

async def get_programme_pmu():
    """Récupère les réunions du jour"""
    date_str = datetime.now().strftime("%d%m%20%y")
    url = f"https://online.pmu.fr/api/client/v1/programme/{date_str}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        return r.json().get('programme', {}).get('reunions', [])

async def get_courses_reunion(id_reunion):
    """Récupère les courses d'une réunion spécifique"""
    date_str = datetime.now().strftime("%d%m%20%y")
    # Format PMU : date + R + numéro (ex: 19032026R1)
    url = f"https://online.pmu.fr/api/client/v1/programme/{date_str}/R{id_reunion}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        return r.json().get('reunion', {}).get('courses', [])

# --- MENUS DE NAVIGATION ---

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("🏇 Trot (LeTrot)", callback_data='menu_trot'),
         InlineKeyboardButton("🐎 Galop (France Galop)", callback_data='menu_galop')],
        [InlineKeyboardButton("📅 Programme & Courses du Jour", callback_data='prog_reunions')],
        [InlineKeyboardButton("ℹ️ Aide", callback_data='aide')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- GESTION DU WEBHOOK ---

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)

        if update.callback_query:
            query = update.callback_query
            await query.answer()

            # 1. Liste des Réunions
            if query.data == 'prog_reunions':
                reunions = await get_programme_pmu()
                keyboard = []
                msg = "📍 **REUNIONS DU JOUR**\nCliquez pour voir les courses :"
                for r in reunions:
                    label = f"R{r['numReunion']} - {r['hippodrome']['libelleShort']} ({r['nature']})"
                    keyboard.append([InlineKeyboardButton(label, callback_data=f"reu_{r['numReunion']}")])
                keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data='back_home')])
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

            # 2. Liste des Courses d'une Réunion
            elif query.data.startswith('reu_'):
                num_reu = query.data.split('_')[1]
                courses = await get_courses_reunion(num_reu)
                keyboard = []
                msg = f"🏁 **COURSES R{num_reu}**\nSélectionnez une course :"
                row = []
                for i, c in enumerate(courses):
                    btn = InlineKeyboardButton(f"C{c['numCourse']}", callback_data=f"course_{num_reu}_{c['numCourse']}")
                    row.append(btn)
                    if len(row) == 4: # 4 boutons par ligne pour la clarté
                        keyboard.append(row)
                        row = []
                if row: keyboard.append(row)
                keyboard.append([InlineKeyboardButton("⬅️ Retour aux réunions", callback_data='prog_reunions')])
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

            # 3. Retour Accueil
            elif query.data == 'back_home':
                await query.edit_message_text("🏇 **STATSTURF PORTAL**", reply_markup=menu_principal())

        elif update.message and update.message.text:
            if update.message.text == "/start":
                await bot.send_message(update.message.chat_id, "🚀 **BIENVENUE SUR STATSTURF**", reply_markup=menu_principal())

        return {"ok": True}
    except Exception as e:
        logger.error(f"Erreur: {e}")
        return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
