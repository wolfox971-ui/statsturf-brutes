import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Bot, Update
from bs4 import BeautifulSoup

# Logs simplifiés pour éviter le rouge inutile
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')

# On initialise uniquement le Bot (plus robuste que l'Application)
bot = Bot(token=TOKEN)

async def get_trot_stats(nom_cheval: str):
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(url, headers=headers)
        if res.status_code != 200:
            return f"❌ Cheval non trouvé ({res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        gains = "Non trouvé"
        for s in soup.find_all(['strong', 'td']):
            if "Gains" in s.text:
                gains = s.find_next().text.strip()
                break
        return f"🏇 **{nom_cheval.upper()}**\n💰 Gains : {gains}\n🔗 {url}"
    except Exception as e:
        return f"⚠️ Erreur : {str(e)}"

@app.post("/webhook")
async def process_webhook(request: Request):
    try:
        data = await request.json()
        # On initialise l'update manuellement
        update = Update.de_json(data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            
            # Traitement manuel des commandes (Zéro erreur d'initialisation)
            if text.startswith("/start"):
                await bot.send_message(chat_id=chat_id, text="✅ Bot opérationnel ! Tape /trot Nom")
            
            elif text.startswith("/trot"):
                nom = text.replace("/trot", "").strip()
                if not nom:
                    await bot.send_message(chat_id=chat_id, text="Exemple : /trot Bold Eagle")
                else:
                    # On envoie un petit message de patience
                    await bot.send_message(chat_id=chat_id, text=f"🔍 Recherche de {nom}...")
                    result = await get_trot_stats(nom)
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown")
        
        return {"ok": True}
    except Exception as e:
        # On log l'erreur en INFO pour éviter le rouge si possible
        logger.info(f"Traitement update : {e}")
        return {"ok": True} # On renvoie quand même OK pour que Telegram arrête d'envoyer l'update

@app.on_event("startup")
async def on_startup():
    if TOKEN and WEBHOOK_URL:
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        logger.info("🚀 Système prêt.")

@app.get("/")
async def health():
    return {"status": "online"}
