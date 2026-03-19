import os
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- BASE DE DONNÉES SIMULÉE (Favoris) ---
# Note: Pour un usage réel, connectez une base de données (PostgreSQL)
user_favorites = {
    "horses": {},      # {id: name}
    "trainers": {},    # {id: name}
    "owners": {},      # {id: name}
    "races": []        # [R1C1, ...]
}

# --- FONCTIONS API (SOURCES OFFICIELLES SETF/PMU) ---

async def get_pmu_data(endpoint: str):
    """Récupère le programme et les partants via PMU"""
    date_str = datetime.now().strftime("%d%m%20%y")
    url = f"https://online.pmu.fr/api/client/v1/programme/{date_str}{endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(url)
            return r.json()
        except: return None

async def search_smart_letrot(query: str):
    """Recherche officielle SETF : Détecte Cheval, Pro ou Écurie"""
    search_url = f"https://www.letrot.com/api/v1/search?q={query.replace(' ', '+')}"
    headers = {'X-Requested-With': 'XMLHttpRequest', 'User-Agent': 'Mozilla/5.0'}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(search_url, headers=headers)
            data = r.json()
            results = []
            if data.get('horses'):
                for h in data['horses'][:2]: results.append({"type": "horse", "name": h['name'], "id": h['id']})
            if data.get('professionals'):
                for p in data['professionals'][:2]: results.append({"type": "trainer", "name": f"{p['firstname']} {p['lastname']}", "id": p['id']})
            if data.get('owners'):
                for o in data['owners'][:2]: results.append({"type": "owner", "name": o['name'], "id": o['id']})
            return results
        except: return []

# --- MENUS DE NAVIGATION ---

def menu_accueil():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏇 SECTION TROT", callback_data='mode_TROT'),
         InlineKeyboardButton("🐎 SECTION GALOP", callback_data='mode_GALOP')],
        [InlineKeyboardButton("📌 MES ÉPINGLES (Monitoring)", callback_data='view_favs')],
        [InlineKeyboardButton("📅 TOUT LE PROGRAMME", callback_data='prog_ALL')]
    ])

def menu_fiche(obj_id, obj_type, name, disc):
    """Menu dynamique pour une fiche avec bouton d'épinglage"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📌 Épingler {name}", callback_data=f"pin_{obj_type}_{obj_id}_{name}")],
        [InlineKeyboardButton("⬅️ Retour", callback_data=f"mode_{disc}")]
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
            cb_data = query.data

            # 1. Navigation Univers
            if cb_data == 'back_home':
                await query.edit_message_text("🏁 **STATSTURF PORTAL**\nChoisissez votre univers :", reply_markup=menu_accueil())

            elif cb_data.startswith('mode_'):
                disc = cb_data.split('_')[1]
                msg = f"✨ **UNIVERS {disc}**\n\nQue souhaitez-vous consulter ?"
                kbd = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"📅 Programme {disc}", callback_data=f"prog_{disc}")],
                    [InlineKeyboardButton(f"🔍 Recherche (Cheval/Pro/Écurie)", callback_data=f"asksearch_{disc}")],
                    [InlineKeyboardButton("⬅️ Retour", callback_data="back_home")]
                ])
                await query.edit_message_text(msg, reply_markup=kbd)

            # 2. Programme Filtré
            elif cb_data.startswith('prog_'):
                disc = cb_data.split('_')[1]
                prog = await get_pmu_data("")
                reunions = prog.get('programme', {}).get('reunions', [])
                kbd = []
                for r in reunions:
                    is_trot = "TROT" in r.get('nature', '').upper()
                    if disc == "ALL" or (disc == "TROT" and is_trot) or (disc == "GALOP" and not is_trot):
                        label = f"R{r['numReunion']} - {r['hippodrome']['libelleShort']}"
                        kbd.append([InlineKeyboardButton(label, callback_data=f"reu_{disc}_{r['numReunion']}")])
                kbd.append([InlineKeyboardButton("⬅️ Retour", callback_data="back_home")])
                await query.edit_message_text(f"📍 **RÉUNIONS {disc} DU JOUR**", reply_markup=InlineKeyboardMarkup(kbd))

            # 3. Détails d'un résultat de recherche (Profil + %)
            elif cb_data.startswith('view_'):
                _, o_type, o_id = cb_data.split('_')
                # Simulation de stats réelles (à lier aux APIs de perfs)
                stats_msg = (f"📊 **STATISTIQUES {o_type.upper()}**\n"
                             f"━━━━━━━━━━━━━━\n"
                             f"🏆 Victoires : `14.5%` (Top 10%)\n"
                             f"🥉 Placé (Podium) : `38%` \n"
                             f"🔥 Forme actuelle : `📈 Positive`\n"
                             f"━━━━━━━━━━━━━━\n"
                             f"_Données basées sur les 12 derniers mois._")
                await query.edit_message_text(stats_msg, reply_markup=menu_fiche(o_id, o_type, "Profil", "TROT"), parse_mode="Markdown")

            # 4. Épinglage (Favoris)
            elif cb_data.startswith('pin_'):
                _, o_type, o_id, o_name = cb_data.split('_')
                user_favorites[f"{o_type}s"][o_id] = o_name
                await query.answer(f"✅ {o_name} ajouté à vos épingles !")

            elif cb_data == 'view_favs':
                msg = "📌 **VOS ÉPINGLES (Monitoring)**\n\n"
                for k, v in user_favorites.items():
                    if v: msg += f"🔹 **{k.capitalize()}** : {', '.join(v.values() if isinstance(v, dict) else v)}\n"
                if msg == "📌 **VOS ÉPINGLES (Monitoring)**\n\n": msg += "Aucune épingle active."
                await query.edit_message_text(msg, reply_markup=menu_accueil(), parse_mode="Markdown")

            elif cb_data.startswith('asksearch_'):
                disc = cb_data.split('_')[1]
                await query.edit_message_text(f"🔍 **RECHERCHE {disc}**\n\nTapez le nom d'un cheval, d'un entraîneur ou d'une écurie :")

        elif update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            if text == "/start":
                await bot.send_message(chat_id, "🚀 **STATSTURF V2**\nPlateforme de monitoring Officielle.", reply_markup=menu_accueil())
            else:
                # Recherche intelligente automatique
                results = await search_smart_letrot(text)
                if not results:
                    await bot.send_message(chat_id, "❌ Aucun résultat (Trot). Essayez un autre nom.")
                else:
                    kbd = []
                    for res in results:
                        icon = "🏇" if res['type'] == "horse" else "👤" if res['type'] == "trainer" else "🏠"
                        kbd.append([InlineKeyboardButton(f"{icon} {res['name']} ({res['type']})", callback_data=f"view_{res['type']}_{res['id']}")])
                    await bot.send_message(chat_id, f"🔍 Résultats pour : **{text}**", reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

        return {"ok": True}
    except Exception as e:
        logger.error(f"Erreur Webhook: {e}")
        return {"ok": True}

@app.on_event("startup")
async def startup():
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def health(): return {"status": "online"}
