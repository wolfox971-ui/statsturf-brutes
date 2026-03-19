import os
import httpx
from fastapi import FastAPI, Request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup

app = FastAPI()
TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)

# --- NAVIGATION INTERACTIVE ---

def menu_principal():
    keyboard = [
        [InlineKeyboardButton("🔍 Rechercher un trotteur", callback_data='search_start')],
        [InlineKeyboardButton("📅 Courses du jour", callback_data='races_today')]
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_cheval(horse_id, nom):
    # Ici on crée une navigation interne au bot
    keyboard = [
        [
            InlineKeyboardButton("📊 Performances", callback_data=f"perf_{horse_id}"),
            InlineKeyboardButton("🧬 Généalogie", callback_data=f"gene_{horse_id}")
        ],
        [InlineKeyboardButton("⬅️ Retour", callback_data="search_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- APPELS API OFFICIELS (SETF) ---

async def get_official_horse_data(nom: str):
    # On utilise l'endpoint de recherche JSON officiel de LeTrot
    search_url = f"https://www.letrot.com/api/v1/search?q={nom.replace(' ', '+')}"
    headers = {'X-Requested-With': 'XMLHttpRequest', 'User-Agent': 'Mozilla/5.0'}
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. On cherche l'ID interne du cheval
        r = await client.get(search_url, headers=headers)
        data = r.json()
        
        if not data.get('horses'):
            return None
        
        horse = data['horses'][0] # On prend le premier résultat
        h_id = horse['id']
        
        # 2. On récupère la fiche détaillée (JSON direct, pas de HTML)
        details_url = f"https://www.letrot.com/api/v1/horse/{h_id}"
        det = await client.get(details_url, headers=headers)
        d = det.json()
        
        return {
            "id": h_id,
            "nom": d['name'],
            "gains": f"{d['total_gains']:,} €".replace(',', ' '),
            "record": d['best_record'] or "Aucun",
            "entraineur": d['trainer_name']
        }

# --- GESTION DES ACTIONS (CALLBACKS) ---

@app.post("/webhook")
async def handle_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    
    # 1. Si l'utilisateur clique sur un bouton
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == "search_start":
            await query.edit_message_text("✍️ Tapez le nom du cheval (ex: Idao de Tillard) :")
            
        elif query.data.startswith("perf_"):
            h_id = query.data.split('_')[1]
            # Ici on appellerait l'API des courses pour ce cheval
            await query.edit_message_text(f"📈 Chargement des dernières courses pour l'ID {h_id}...")

    # 2. Si l'utilisateur envoie un texte
    elif update.message and update.message.text:
        text = update.message.text
        if text == "/start":
            await bot.send_message(update.message.chat_id, "🏇 **LE TROTTEUR FRANÇAIS**\n_Données officielles SETF_", 
                                 reply_markup=menu_principal(), parse_mode="Markdown")
        else:
            res = await get_official_horse_data(text)
            if res:
                msg = (f"🏇 **{res['nom']}**\n"
                       f"━━━━━━━━━━━━━━\n"
                       f"💰 Gains : `{res['gains']}`\n"
                       f"🏆 Record : `{res['record']}`\n"
                       f"👤 Entraîneur : {res['entraineur']}")
                await bot.send_message(update.message.chat_id, msg, 
                                     reply_markup=menu_cheval(res['id'], res['nom']), parse_mode="Markdown")
            else:
                await bot.send_message(update.message.chat_id, "❌ Cheval introuvable sur LeTrot.")

    return {"ok": True}
