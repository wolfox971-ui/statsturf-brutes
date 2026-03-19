import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Bot, Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- INTERFACE : BOUTONS ---
def get_main_menu():
    # Boutons permanents en bas de l'écran
    keyboard = [['🏇 Rechercher un cheval', '📊 Aide']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_details_button(url):
    # Bouton cliquable sous le résultat
    keyboard = [[InlineKeyboardButton("🔍 Voir la fiche LeTrot", url=url)]]
    return InlineKeyboardMarkup(keyboard)

# --- FONCTION DE SCRAPING ---
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
            return None, f"❌ Impossible de trouver **{nom_cheval}** sur LeTrot."
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def find_data(label):
            elem = soup.find(string=lambda t: label in t if t else False)
            return elem.find_next().text.strip() if elem else "Non disponible"

        gains = find_data("Gains cumulés")
        record = find_data("Record")
        
        msg = (f"🏇 **{nom_cheval.upper()}**\n"
               f"━━━━━━━━━━━━━━\n"
               f"💰 **Gains :** `{gains}`\n"
               f"🏆 **Record :** `{record}`\n"
               f"━━━━━━━━━━━━━━")
        return url, msg
                
    except Exception:
        return None, "⚠️ Erreur technique (LeTrot est peut-être saturé)."

# --- GESTION DU WEBHOOK ---
@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id

            if text == "/start" or text == "📊 Aide":
                await bot.send_message(
                    chat_id=chat_id,
                    text="👋 **Bienvenue sur StatsTurf !**\n\nUtilisez le menu ci-dessous pour commencer.",
                    reply_markup=get_main_menu(),
                    parse_mode="Markdown"
                )

            elif text == "🏇 Rechercher un cheval":
                await bot.send_message(chat_id=chat_id, text="✍️ Envoyez-moi le nom d'un cheval (ex: *Bold Eagle*) :", parse_mode="Markdown")

            else:
                # On traite le texte comme un nom de cheval
                wait_msg = await bot.send_message(chat_id=chat_id, text=f"🔍 Recherche de **{text}**...", parse_mode="Markdown")
                url, result = await get_trot_stats(text)
                
                if url:
                    await bot.send_message(chat_id=chat_id, text=result, reply_markup=get_details_button(url), parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown")
                
                await bot.delete_message(chat_id=chat_id, message_id=wait_msg.message_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"ok": True}

@app.on_event("startup")
async def startup_event():
    if TOKEN and WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def root():
    return {"status": "Bot is running"}
