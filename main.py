from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

# Récupération des variables d'environnement
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    print("❌ ERREUR: TOKEN ou WEBHOOK_URL manquant !")

bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

async def get_trot_stats(nom_cheval: str):
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=15.0)
            
        if res.status_code != 200:
            return f"❌ Cheval non trouvé (Code {res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Exemple de recherche de données (à adapter selon le HTML de LeTrot)
        def find_data(label):
            elem = soup.find(string=lambda t: label in t if t else False)
            return elem.find_next().text.strip() if elem else "N/A"

        gains = find_data("Gains cumulés")
        rec = find_data("Record")
        
        return f"🏇 **TROT - {nom_cheval.upper()}**\n💰 Gains : {gains}\n🏆 Record : {rec}\n🔗 [Fiche]({url})"
    except Exception as e:
        return f"⚠️ Erreur : {str(e)}"

async def trot_fiche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage : /trot_fiche Nom")
        return
    nom = " ".join(context.args)
    msg = await update.message.reply_text("🔍 Recherche...")
    result = await get_trot_stats(nom)
    await msg.edit_text(result, parse_mode="Markdown")

application.add_handler(CommandHandler("trot_fiche", trot_fiche))

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup():
    await application.initialize()
    await application.start()
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"✅ Webhook configuré sur {WEBHOOK_URL}")

@app.get("/")
async def home():
    return {"status": "Bot actif"}
