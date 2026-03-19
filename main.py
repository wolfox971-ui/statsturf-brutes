from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio
import httpx
from bs4 import BeautifulSoup

app = FastAPI()

# Configuration (Variables Railway)
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Initialisation du bot et de l'application
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

# --- FONCTION SCRAPING ---
async def get_trot_stats(nom_cheval: str):
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=headers, timeout=15.0)
            
        if res.status_code != 200:
            return f"❌ Cheval non trouvé sur LeTrot (Code {res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        def find_data(label):
            elem = soup.find(string=lambda t: label in t if t else False)
            return elem.find_next().text.strip() if elem else "Non trouvé"

        gains = find_data("Gains cumulés")
        rec = find_data("Record")
        
        return (f"🏇 **TROT - {nom_cheval.upper()}**\n"
                f"💰 Gains : {gains}\n"
                f"🏆 Record : {rec}\n"
                f"🔗 [Fiche complète]({url})")
    except Exception as e:
        return f"⚠️ Erreur scraping : {str(e)}"

# --- COMMANDES TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bonjour ! Envoie-moi /trot_fiche suivi du nom d'un cheval.")

async def trot_fiche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Syntaxe : /trot_fiche Bold Eagle")
        return
    
    nom = " ".join(context.args)
    wait_msg = await update.message.reply_text(f"🔍 Recherche de '{nom}' sur LeTrot...")
    
    result = await get_trot_stats(nom)
    await wait_msg.edit_text(result, parse_mode="Markdown")

# Ajout des handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("trot_fiche", trot_fiche))

# --- ROUTES FASTAPI ---
@app.post("/webhook")
async def webhook_handler(request: Request):
    """Réception des messages de Telegram"""
    # CRITIQUE : Assure que le bot est initialisé AVANT de traiter le message
    if not application.running:
        await application.initialize()
        await application.start()
    
    try:
        data = await request.json()
        update = Update.de_json(data, bot)
        await application.process_update(update)
    except Exception as e:
        print(f"Erreur traitement update: {e}")
        
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    """Lancement au démarrage de Railway"""
    await application.initialize()
    await application.start()
    # On force l'URL du webhook auprès de Telegram
    webhook_final_url = f"{WEBHOOK_URL}/webhook"
    await bot.set_webhook(url=webhook_final_url)
    print(f"🚀 Webhook configuré sur : {webhook_final_url}")

@app.get("/")
async def health_check():
    return {"status": "Bot opérationnel", "url": WEBHOOK_URL}
