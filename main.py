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

# --- BOUTONS ---
def main_menu_keyboard():
    # Boutons en bas du clavier
    keyboard = [['🏇 Rechercher un cheval', '📊 Aide']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def link_keyboard(url):
    # Bouton cliquable sous le message
    keyboard = [[InlineKeyboardButton("🔍 Voir la fiche complète", url=url)]]
    return InlineKeyboardMarkup(keyboard)

# --- SCRAPING ---
async def get_trot_stats(nom_cheval: str):
    nom_clean = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_clean}/courses"
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
        'Referer': 'https://www.letrot.com/'
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            res = await client.get(url, headers=headers)
        
        if res.status_code != 200:
            return None, f"❌ Désolé, je ne trouve pas de fiche pour **{nom_cheval}**."
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def find_val(text_search):
            elem = soup.find(string=lambda t: text_search in t if t else False)
            return elem.find_next().text.strip() if elem else "N/A"

        gains = find_val("Gains cumulés")
        record = find_val("Record")
        
        text = (f"✨ **RÉSULTATS POUR {nom_cheval.upper()}** ✨\n\n"
                f"💰 **Gains totaux :** `{gains}`\n"
                f"🏆 **Meilleur record :** `{record}`\n\n"
                f"💡 _Cliquez sur le bouton ci-dessous pour plus de détails._")
        return url, text
                
    except Exception:
        return None, "⚠️ Le service LeTrot est indisponible pour le moment."

# --- WEBHOOK ---
@app.post("/webhook")
async def process_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message:
            chat_id = update.message.chat_id
            text = update.message.text

            # Gestion du menu
            if text == "/start" or text == "📊 Aide":
                await bot.send_message(
                    chat_id=chat_id, 
                    text="👋 **Bienvenue sur StatsTurf !**\n\nCliquez sur le bouton ci-dessous ou tapez le nom d'un cheval.",
                    reply_markup=main_menu_keyboard(),
                    parse_mode="Markdown"
                )

            elif text == "🏇 Rechercher un cheval":
                await bot.send_message(chat_id=chat_id, text="✍️ Envoyez-moi le **nom du cheval** (ex: Bold Eagle) :")

            else:
                # On considère que tout autre texte est une recherche de cheval
                nom = text.strip()
                waiting = await bot.send_message(chat_id=chat_id, text=f"⏳ Analyse de **{nom}**...")
                
                url, result = await get_trot_stats(nom)
                
                if url:
                    await bot.send_message(
                        chat_id=chat_id, 
                        text=result, 
                        reply_markup=link_keyboard(url), 
                        parse_mode="Markdown"
                    )
                else:
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown")
                
                await bot.delete_message(chat_id=chat_id, message_id=waiting.message_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"ok": True}

@app.on_event("startup")
async def on_startup():
    if TOKEN and WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def health():
    return {"status": "ok"}
