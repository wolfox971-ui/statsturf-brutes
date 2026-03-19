import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

# Configuration des logs pour Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- BASE DE DONNÉES TEMPORAIRE (Favoris) ---
# Note: En production, on utiliserait une vraie base comme PostgreSQL
user_favorites = {
    "horses": [],    # Liste des IDs chevaux épinglés
    "trainers": [],  # Liste des noms d'entraîneurs épinglés
    "races": []      # IDs des courses suivies en direct
}

# --- FONCTIONS API (SOURCES OFFICIELLES) ---

async def get_pmu_data(endpoint: str):
    """Interroge l'API PMU pour le programme et les partants"""
    date_str = datetime.now().strftime("%d%m%20%y")
    url = f"https://online.pmu.fr/api/client/v1/programme/{date_str}{endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            return r.json()
        except Exception as e:
            logger.error(f"Erreur API PMU: {e}")
            return None

# --- MENUS DE NAVIGATION ---

def menu_accueil():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏇 SECTION TROT", callback_data='mode_TROT')],
        [InlineKeyboardButton("🐎 SECTION GALOP", callback_data='mode_GALOP')],
        [InlineKeyboardButton("📌 MES ÉPINGLES (Favoris)", callback_data='view_favs')],
        [InlineKeyboardButton("ℹ️ Aide", callback_data='help')]
    ])

def menu_discipline(disc):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 Programme {disc}", callback_data=f'prog_{disc}')],
        [InlineKeyboardButton(f"🔍 Chercher un {disc}", callback_data=f'search_{disc}')],
        [InlineKeyboardButton("⬅️ Retour Accueil", callback_data='back_home')]
    ])

# --- GESTION DU WEBHOOK ---

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)

        if update.callback_query:
            query = update.callback_query
            await query.answer()
            data = query.data

            # 1. Navigation Principale
            if data == 'back_home':
                await query.edit_message_text("🏁 **STATSTURF PORTAL**\nChoisissez votre univers :", reply_markup=menu_accueil())

            elif data.startswith('mode_'):
                disc = data.split('_')[1]
                await query.edit_message_text(f"✨ **UNIVERS {disc}**\nDonnées officielles et monitoring.", reply_markup=menu_discipline(disc))

            # 2. Programme Filtré (Trot ou Galop)
            elif data.startswith('prog_'):
                disc = data.split('_')[1]
                prog_data = await get_pmu_data("")
                reunions = prog_data.get('programme', {}).get('reunions', [])
                
                keyboard = []
                msg = f"📍 **RÉUNIONS {disc} DU JOUR**\n"
                
                for r in reunions:
                    nature = r.get('nature', '').upper()
                    # Filtrage intelligent
                    is_trot = "TROT" in nature
                    if (disc == "TROT" and is_trot) or (disc == "GALOP" and not is_trot):
                        label = f"R{r['numReunion']} - {r['hippodrome']['libelleShort']}"
                        keyboard.append([InlineKeyboardButton(label, callback_data=f"reu_{disc}_{r['numReunion']}")])
                
                keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data=f'mode_{disc}')])
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

            # 3. Liste des Courses d'une Réunion
            elif data.startswith('reu_'):
                _, disc, num_reu = data.split('_')
                reu_details = await get_pmu_data(f"/R{num_reu}")
                courses = reu_details.get('reunion', {}).get('courses', [])
                
                keyboard = []
                msg = f"🏁 **R{num_reu} - COURSES ({disc})**\nCliquez pour voir les partants et les % :"
                
                row = []
                for c in courses:
                    # On affiche l'heure et le numéro
                    btn = InlineKeyboardButton(f"C{c['numCourse']}", callback_data=f"parts_{disc}_{num_reu}_{c['numCourse']}")
                    row.append(btn)
                    if len(row) == 4:
                        keyboard.append(row)
                        row = []
                if row: keyboard.append(row)
                keyboard.append([InlineKeyboardButton("⬅️ Retour Réunions", callback_data=f'prog_{disc}')])
                await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

            # 4. Gestion des Épingles (Favoris)
            elif data.startswith('pin_'):
                _, o_type, o_name = data.split('_')
                if o_name not in user_favorites[f"{o_type}s"]:
                    user_favorites[f"{o_type}s"].append(o_name)
                    await query.answer(f"📌 {o_name} ajouté à vos épingles !")
                else:
                    await query.answer("Déjà dans vos favoris.")

            elif data == 'view_favs':
                msg = "📌 **VOS ÉPINGLES**\n\n"
                msg += "🏇 **Chevaux :** " + (", ".join(user_favorites['horses']) if user_favorites['horses'] else "Aucun") + "\n"
                msg += "👤 **Entraîneurs :** " + (", ".join(user_favorites['trainers']) if user_favorites['trainers'] else "Aucun")
                await query.edit_message_text(msg, reply_markup=menu_accueil(), parse_mode="Markdown")

        elif update.message and update.message.text:
            if update.message.text == "/start":
                await bot.send_message(update.message.chat_id, "🚀 **STATSTURF V2**\n_Outil de monitoring professionnel_", reply_markup=menu_accueil())

        return {"ok": True}
    except Exception as e:
        logger.error(f"Erreur Globale: {e}")
        return {"ok": True}

@app.on_event("startup")
async def startup():
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def health(): return {"status": "operational"}
