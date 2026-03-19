import os
import httpx
import logging
from fastapi import FastAPI, Request
from telegram import Bot, Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from bs4 import BeautifulSoup

# Logs pour surveiller le comportement sur Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
bot = Bot(token=TOKEN)

# --- MISE EN PAGE : BOUTONS ---
def get_main_keyboard():
    # Crée des gros boutons en bas de l'écran Telegram
    keyboard = [['🏇 Rechercher un cheval', '📊 Aide']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_inline_link(url):
    # Crée un bouton cliquable juste sous le résultat
    keyboard = [[InlineKeyboardButton("🔗 Voir la fiche complète", url=url)]]
    return InlineKeyboardMarkup(keyboard)

# --- LOGIQUE DE RECHERCHE ---
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
            return None, f"❌ Désolé, je ne trouve pas de fiche pour **{nom_cheval}**."
        
        soup = BeautifulSoup(res.text, 'html.parser')
