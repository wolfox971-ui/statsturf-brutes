import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Bot, Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup

# Logs pour surveiller le comportement sur Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- MISE EN PAGE : BOUTONS ---
def get_main_keyboard():
    # Crée des gros boutons en bas de l'écran Telegram
    keyboard = [['🏇 Rechercher un cheval', '📊 Aide']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_link(url):
    # Crée un bouton cliquable juste sous le résultat
    keyboard = [[InlineKeyboardButton("🔗 Voir la fiche complète", url=url)]]
    return InlineKeyboardMarkup(keyboard)

# --- LOGIQUE DE RECHERCHE ---
async def get_trot_stats(nom_cheval: str):
    nom_clean = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_clean}/courses"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        'Referer': 'https://www.letrot.com/'
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(url, headers=headers)
        
        if res.status_code != 200:
            return None, f"❌ Désolé, je ne trouve pas de fiche pour **{nom_cheval}**."
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def find_val(label):
            elem = soup.find(string=lambda t: label in t if t else False)
            return elem.find_next().text.strip() if elem else "Non renseigné"

        gains = find_val("Gains cumulés")
        record = find_val("Record")
        
        msg = (f"✨ **RÉSULTATS : {nom_cheval.upper()}** ✨\n\n"
               f"💰 **Gains :** `{gains}`\n"
               f"🏆 **Record :** `{record}`")
        return url, msg
                
    except Exception:
        return None, "⚠️ Erreur de connexion au site LeTrot."

# --- GESTION DES MESSAGES ---
@app.post("/webhook")
async def process_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id

            if text == "/start" or text == "📊 Aide":
                await bot.send_message(
                    chat_id=chat_id,
                    text="👋 **Bienvenue sur StatsTurf !**\n\nUtilisez les boutons ci-dessous ou envoyez simplement le nom d'un cheval.",
                    reply_markup=get_main_keyboard(),
                    parse_mode="Markdown"
                )

            elif text == "🏇 Rechercher un cheval":
                await bot.send_message(chat_id=chat_id, text="✍️ Tapez le nom du cheval (ex: Bold Eagle) :")

            else:
                # Recherche automatique
                waiting = await bot.send_message(chat_id=chat_id, text=f"🔍 Analyse de **{text}**...")
                url, result = await get_trot_stats(text)
                
                if url:
                    await bot.send_message(chat_id=chat_id, text=result, reply_markup=get_inline_link(url), parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown")
                
                # Supprime le message "Analyse en cours" pour rester propre
                await bot.delete_message(chat_id=chat_id, message_id=waiting.message_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Erreur : {e}")
        return {"ok": True}

@app.on_event("startup")
async def on_startup():
    if TOKEN and WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def health():
    return {"status": "online"}
