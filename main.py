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
def main_menu():
    # Crée des boutons persistants en bas du clavier
    return ReplyKeyboardMarkup([['🏇 Rechercher un cheval', 'ℹ️ Aide']], resize_keyboard=True)

def details_button(url):
    # Bouton cliquable sous le message de résultat
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Voir la fiche LeTrot", url=url)]])

# --- SCRAPING ---
async def get_trot_stats(nom_cheval: str):
    nom_clean = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_clean}/courses"
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15'}
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(url, headers=headers)
        
        if res.status_code != 200:
            return None, f"❌ Impossible de trouver **{nom_cheval}**."
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def find_label(label):
            elem = soup.find(string=lambda t: label in t if t else False)
            return elem.find_next().text.strip() if elem else "Non renseigné"

        gains = find_label("Gains cumulés")
        record = find_label("Record")
        
        result_text = (
            f"🏇 **FICHE CHEVAL : {nom_cheval.upper()}**\n"
            f"───────────────────\n"
            f"💰 **Gains :** `{gains}`\n"
            f"🏆 **Record :** `{record}`\n"
            f"───────────────────"
        )
        return url, result_text
    except Exception:
        return None, "⚠️ Erreur lors de la connexion à LeTrot."

# --- GESTION DES MESSAGES ---
@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id

            if text == "/start" or text == "ℹ️ Aide":
                await bot.send_message(
                    chat_id=chat_id,
                    text="👋 **Bienvenue sur StatsTurf !**\n\nUtilisez le menu ci-dessous pour lancer une recherche.",
                    reply_markup=main_menu(),
                    parse_mode="Markdown"
                )

            elif text == "🏇 Rechercher un cheval":
                await bot.send_message(chat_id=chat_id, text="✍️ Envoyez-moi le **nom du cheval** :", parse_mode="Markdown")

            else:
                # On traite le texte comme un nom de cheval
                wait = await bot.send_message(chat_id=chat_id, text=f"🔍 Analyse de **{text}**...", parse_mode="Markdown")
                url, result = await get_trot_stats(text)
                
                if url:
                    await bot.send_message(chat_id=chat_id, text=result, reply_markup=details_button(url), parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown")
                
                await bot.delete_message(chat_id=chat_id, message_id=wait.message_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": True}

@app.on_event("startup")
async def on_startup():
    if TOKEN and WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")

@app.get("/")
async def health():
    return {"status": "ok"}
