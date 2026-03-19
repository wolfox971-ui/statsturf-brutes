from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# Variables d'environnement
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN manquant dans les variables Railway")

CANAL_ID = os.getenv("CANAL_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL manquant")

bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

print(f"✅ Bot démarré - TOKEN OK - WEBHOOK_URL: {WEBHOOK_URL}")

# Fonction scraping Trot simple (à affiner)
def get_trot_stats(nom_cheval: str):
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code != 200:
            return f"❌ Page non trouvée (code {res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Sélecteurs à ajuster – exemples basés sur structure actuelle LeTrot
        gains_elem = soup.find(string="Gains cumulés :")  # texte proche
        gains = gains_elem.find_next('strong').text.strip() if gains_elem else "Non trouvé"
        
        pct_victoires = soup.find(string="Victoires :") 
        pct = pct_victoires.find_next('span').text.strip() if pct_victoires else "N/A"
        
        record = soup.find(string="Record :")
        rec = record.find_next('span').text.strip() if record else "N/A"
        
        return f"""🏇 **TROT - {nom_cheval.upper()}**
💰 Gains cumulés : {gains}
📈 % Victoires : {pct}
🏆 Record : {rec}
🔗 {url}"""
    except Exception as e:
        return f"Erreur scraping : {str(e)}"

# Commande exemple
async def trot_fiche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Utilisation : /trot_fiche Nom Du Cheval")
        return
    
    nom = " ".join(context.args)
    result = get_trot_stats(nom)
    await update.message.reply_text(result, parse_mode="Markdown")

# Ajout des handlers
application.add_handler(CommandHandler("trot_fiche", trot_fiche))

# Webhook
@app.post("/webhook")
async def webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup():
    await application.initialize()
    await application.start()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("Webhook posé avec succès")

    # Test manuel canal (décommente pour tester une fois)
    # await bot.send_message(CANAL_ID, "Test publication canal depuis Railway ✅")

@app.get("/")
async def home():
    return {"status": "Bot actif", "webhook": WEBHOOK_URL}
