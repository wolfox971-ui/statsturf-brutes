import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackContext
import asyncio
from datetime import datetime
import json  # pour cache simple au début

app = FastAPI()
TOKEN = os.getenv("8506445900:AAE9u3TGy_9uHMb-Z0nwDvOWZm45m4e7mME")  # Mets ton token dans les variables d'environnement Railway
CANAL_ID = os.getenv("-1003612357122")  # ex: -1001234567890 (ID du canal)
bot = Bot(token=TOKEN)

# Cache simple (dict en mémoire + fichier JSON optionnel)
cache = {}

def get_trot_stats(nom_cheval: str):
    # À adapter selon structure réelle LeTrot (exemple basé sur site actuel)
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Exemple de sélecteurs (à ajuster après test sur le site réel)
        gains = soup.select_one('.gains-total').text.strip() if soup.select_one('.gains-total') else "N/A"
        victoires_pct = soup.select_one('.pct-victoires').text.strip() if soup.select_one('.pct-victoires') else "N/A"
        record = soup.select_one('.record').text.strip() if soup.select_one('.record') else "N/A"
        
        return f"""🏇 **TROT - {nom_cheval.upper()}**
💰 Gains : {gains}
📈 % Victoires : {victoires_pct}
🏆 Record : {record}
🔗 Source : LeTrot officiel"""
    except:
        return "❌ Erreur lors de la récupération des stats Trot."

def get_galop_stats(nom_cheval: str):
    # À adapter sur Turfoo ou France Galop
    # Exemple placeholder
    return f"""🐎 **GALOP - {nom_cheval.upper()}**
Stats Galop en cours de développement... (Turfoo scraping)"""

# Commandes du bot
async def trot_fiche(update: Update, context: CallbackContext):
    nom = " ".join(context.args) if context.args else "inconnu"
    data = get_trot_stats(nom)
    await update.message.reply_text(data, parse_mode="Markdown")

async def galop_fiche(update: Update, context: CallbackContext):
    nom = " ".join(context.args) if context.args else "inconnu"
    data = get_galop_stats(nom)
    await update.message.reply_text(data, parse_mode="Markdown")

# Tâche automatique quotidienne pour le canal
async def publication_quotidienne():
    now = datetime.now().strftime("%d %B %Y")
    message = f"""📊 **STATS BRUTES TURF - {now}**

🟠 **TROT** (Source LeTrot officiel)
[Stats des réunions du jour - à générer]

🔵 **GALOP** (Source Turfoo / France Galop)
[Stats des réunions du jour - à générer]

🔹 Données objectives uniquement. Vous analysez, vous décidez."""
    
    await bot.send_message(chat_id=CANAL_ID, text=message, parse_mode="Markdown")

# Application Telegram
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("trot_fiche", trot_fiche))
application.add_handler(CommandHandler("galop_fiche", galop_fiche))
# Ajouter d'autres commandes plus tard (/trot_stats_jockey, etc.)

@app.on_event("startup")
async def startup_event():
    await application.initialize()
    await application.start()
    # Set webhook
    webhook_url = os.getenv("WEBHOOK_URL")  # ex: https://ton-projet.railway.app/webhook
    await bot.set_webhook(webhook_url + "/webhook")
    
    # Planifier la publication quotidienne (exemple APScheduler à ajouter)
    print("Bot démarré avec webhook + publication planifiée")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"status": "ok"}

# Pour tester localement ou ajouter scheduler
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
