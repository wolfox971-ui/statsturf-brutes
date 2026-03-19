import logging
import sqlite3
import requests
import os
import datetime
from bs4 import BeautifulSoup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_PATH = '/app/data/turfa_pro.db' if os.path.exists('/app/data') else 'turfa_pro.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS favoris 
                        (user_id INTEGER, type TEXT, nom TEXT, UNIQUE(user_id, type, nom))''')

# --- SCRAPER PRO (Cotes & Heures) ---
def get_horse_data(nom):
    nom_clean = nom.strip().replace(" ", "-").lower()
    url = f"https://www.pmu.fr/turf/cheval/{nom_clean}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # Détection du statut de course
        txt = soup.get_text()
        return {
            "nom": nom.upper(),
            "m_c": soup.select_one('.musique').text if soup.select_one('.musique') else "N/A",
            "coach": soup.select_one('.trainer').text.strip() if soup.select_one('.trainer') else "Inconnu",
            "proprio": soup.select_one('.owner').text.strip() if soup.select_one('.owner') else "Inconnu",
            "origines": soup.select_one('.father').text if soup.select_one('.father') else "N/A",
            "cote": soup.select_one('.cote').text if soup.select_one('.cote') else "N/C",
            "today": "Prochaine course" in txt or "Partant" in txt,
            "heure": "15h45" # Simulation : PMU charge l'heure via JS, nécessite API ou Selenium pour le réel
        }
    except: return None

# --- TÂCHES AUTOMATIQUES (Alertes & Bilans) ---

async def alerte_matin_et_minute(context: ContextTypes.DEFAULT_TYPE):
    """Vérifie les favoris à 08h00 et programme les alertes cotes"""
    with sqlite3.connect(DB_PATH) as conn:
        users = conn.execute("SELECT DISTINCT user_id FROM favoris").fetchall()
    
    for (uid,) in users:
        with sqlite3.connect(DB_PATH) as conn:
            favs = conn.execute("SELECT nom FROM favoris WHERE user_id = ?", (uid,)).fetchall()
        
        partants = []
        for (nom,) in favs:
            data = get_horse_data(nom)
            if data and data['today']:
                partants.append(nom)
                # Programmation Alerte 15min avant (Simulé ici car l'heure réelle PMU est dynamique)
                # context.job_queue.run_once(send_last_minute, when=...)
        
        if partants:
            await context.bot.send_message(uid, f"☀️ **MATINALE :** {len(partants)} chevaux courent aujourd'hui !\n" + "\n".join([f"🏇 **{n}**" for n in partants]), parse_mode='Markdown')

async def bilan_soir(context: ContextTypes.DEFAULT_TYPE):
    """Envoie le récap des résultats à 19h00"""
    # Ici on pourrait scraper les arrivées du jour
    await context.bot.send_message(context.job.chat_id, "🏁 **BILAN DU SOIR**\nConsultez vos favoris pour voir les nouvelles musiques à jour !", parse_mode='Markdown')

# --- GESTIONNAIRES ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🔍 Analyser", callback_data='search')],
          [InlineKeyboardButton("⭐ Favoris", callback_data='favs')]]
    txt = "🏇 **TURFA MASTER v10**\n_Alertes 08:00 & Bilan 19:00 actifs._"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nom = update.message.text.upper()
    try: await update.message.delete()
    except: pass
    
    status = await update.effective_chat.send_message(f"📡 Analyse de **{nom}**...")
    data = get_horse_data(nom)
    
    if data:
        txt = (f"🏇 **{data['nom']}** | Cote: `{data['cote']}`\n🧬 `{data['origines']}`\n━━━━━━━━━━━━━━━\n"
               f"📈 Musique : `{data['m_c']}`\n👤 Proprio : {data['proprio']}\n👔 Coach : {data['coach']}\n━━━━━━━━━━━━━━━")
        kb = [[InlineKeyboardButton("📌 Épingler", callback_data=f"save_{nom}")],
              [InlineKeyboardButton("⬅️ Retour", callback_data='back')]]
        await status.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    else:
        await status.edit_text(f"❌ **{nom}** non trouvé.")

async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == 'search':
        await query.edit_message_text("✍️ Envoyez le nom du cheval...")
    
    elif query.data.startswith('save_'):
        nom = query.data.split('_')[1]
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO favoris VALUES (?, 'C', ?)", (uid, nom))
        await context.bot.send_message(chat_id=uid, text=f"✅ {nom} épinglé")

    elif query.data == 'favs':
        with sqlite3.connect(DB_PATH) as conn:
            favs = conn.execute("SELECT nom FROM favoris WHERE user_id = ?", (uid,)).fetchall()
        
        if not favs:
            await query.edit_message_text("📂 Aucune épingle.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Retour", callback_data='back')]]))
            return

        kb = [[InlineKeyboardButton(f"❌ {f[0]}", callback_data=f"del_{f[0]}")] for f in favs]
        kb.append([InlineKeyboardButton("⬅️ Retour", callback_data='back')])
        await query.edit_message_text("⭐ **VOS ÉPINGLÉS :**", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith('del_'):
        nom = query.data.replace('del_', '')
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM favoris WHERE user_id = ? AND nom = ?", (uid, nom))
        query.data = 'favs'
        await button_router(update, context)

    elif query.data == 'back':
        await start(update, context)

# --- LANCEMENT ---
if __name__ == '__main__':
    init_db()
    TOKEN = os.getenv("TOKEN")
    app = Application.builder().token(TOKEN).build()

    # Planification des Jobs
    if app.job_queue:
        # Alerte matinale à 08h00
        app.job_queue.run_daily(alerte_matin_et_minute, time=datetime.time(hour=8, minute=0))
        # Bilan du soir à 19h00
        app.job_queue.run_daily(bilan_soir, time=datetime.time(hour=19, minute=0))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🚀 TURFA MASTER v10 LANCÉ SUR RAILWAY")
    app.run_polling()
