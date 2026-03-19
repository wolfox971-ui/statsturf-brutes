import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Bot, Update
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

async def get_trot_stats(nom_cheval: str):
    # Transformation du nom pour l'URL LeTrot
    nom_clean = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_clean}/courses"
    
    # Headers ultra-complets pour éviter le 404/403
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr-FR,fr;q=0.9',
        'Referer': 'https://www.letrot.com/'
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            res = await client.get(url, headers=headers)
        
        if res.status_code != 200:
            return f"❌ Impossible d'accéder à la fiche de {nom_cheval} (Erreur {res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Extraction des données
        def find_val(text_search):
            elem = soup.find(string=lambda t: text_search in t if t else False)
            return elem.find_next().text.strip() if elem else "Non trouvé"

        gains = find_val("Gains cumulés")
        record = find_val("Record")
        
        return (f"🏇 **{nom_cheval.upper()}**\n"
                f"💰 Gains : `{gains}`\n"
                f"🏆 Record : `{record}`\n\n"
                f"🔗 [Voir sur LeTrot]({url})")
                
    except Exception as e:
        return f"⚠️ Erreur de connexion : {str(e)}"

@app.post("/webhook")
async def process_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        
        if update.message and update.message.text:
            text = update.message.text
            chat_id = update.message.chat_id
            
            if text.startswith("/start"):
                await bot.send_message(chat_id=chat_id, text="✅ Bot Turf prêt !\nUtilise : `/trot Nom du cheval`", parse_mode="Markdown")
            
            elif text.startswith("/trot"):
                nom = text.replace("/trot", "").strip()
                if not nom:
                    await bot.send_message(chat_id=chat_id, text="Format : `/trot Bold Eagle`", parse_mode="Markdown")
                else:
                    await bot.send_message(chat_id=chat_id, text=f"🔍 Analyse de **{nom}**...", parse_mode="Markdown")
                    result = await get_trot_stats(nom)
                    await bot.send_message(chat_id=chat_id, text=result, parse_mode="Markdown", disable_web_page_preview=False)
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
