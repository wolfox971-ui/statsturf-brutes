import os
import asyncio
import httpx
import logging
from fastapi import FastAPI, Request, BackgroundTasks
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from bs4 import BeautifulSoup

# Configuration des logs pour voir tout dans Railway
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Variables d'environnement
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')

if not TOKEN:
    raise ValueError("❌ Erreur : Variable TOKEN manquante !")

# Initialisation
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

# --- SCRAPING LETROT ---
async def get_trot_stats(nom_cheval: str):
    nom_url = nom_cheval.strip().replace(" ", "-").upper()
    url = f"https://www.letrot.com/stats/chevaux/{nom_url}/courses"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            
        if res.status_code != 200:
            return f"❌ Cheval non trouvé ou site bloqué (Code {res.status_code})"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Tentative d'extraction des gains (Sélecteurs larges)
        gains = "Non trouvé"
        possible_labels = ["Gains cumulés", "Gains", "Total des gains"]
        
        for label in possible_labels:
            label_elem = soup.find(string=lambda t: label in t if t else False)
            if label_elem:
                val = label_elem.find_next()
                if val:
                    gains = val.text.strip()
                    break

        return f"🏇 **TROT - {nom_cheval.upper()}**\n💰 Gains : {gains}\n🔗 [Fiche LeTrot]({url})"
    except Exception as e:
        logger.error(f"Erreur scraping: {e}")
        return f"⚠️ Erreur technique lors du scraping."

# --- HANDLERS TELEGRAM ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot actif ! Utilise /trot_fiche [Nom]")

async def trot_fiche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /trot_fiche Bold Eagle")
        return
    
    nom = " ".join(context.args)
    temp_msg = await update.message.reply_text(f"🔍 Analyse de {nom}...")
    
    resultat = await get_trot_stats(nom)
    await temp_msg.edit_text(resultat, parse_mode="Markdown")

# Enregistrement des commandes
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("trot_fiche", trot_fiche))

# --- ROUTES WEBHOOK ---
@app.post("/webhook")
async def process_update(request: Request, background_tasks: BackgroundTasks):
    """Reçoit les updates de Telegram et répond 200 OK immédiatement"""
    try:
        # On s'assure que le bot est "réveillé"
        if not application.running:
            await application.initialize()
            await application.start()

        payload = await request.json()
        update = Update.de_json(payload, bot)
        
        # On lance le traitement en tâche de fond pour libérer FastAPI
        background_tasks.add_task(application.process_update, update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Erreur Webhook: {e}")
        return {"ok": False, "error": str(e)}

@app.on_event("startup")
async def on_startup():
    """Configuré au lancement du serveur Railway"""
    await application.initialize()
    await application.start()
    
    if WEBHOOK_URL:
        full_url = f"{WEBHOOK_URL}/webhook"
        await bot.set_webhook(url=full_url)
        logger.info(f"🚀 Webhook enregistré : {full_url}")
    else:
        logger.warning("⚠️ WEBHOOK_URL n'est pas configuré !")

@app.get("/")
async def health():
    return {"status": "running", "webhook_url": WEBHOOK_URL}
