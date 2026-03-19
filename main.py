from fastapi import FastAPI
import os

app = FastAPI()

# Vérification obligatoire du TOKEN
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("❌ TOKEN manquant ! Ajoute-le dans Variables sur Railway")

print("✅ TOKEN chargé correctement")
print(f"WEBHOOK_URL : {os.getenv('WEBHOOK_URL')}")

# Le reste du code (bot, commandes, etc.) viendra après

@app.get("/")
async def home():
    return {
        "status": "Bot StatsTurf Brutes EN LIGNE",
        "message": "Tout est bon, plus de crash TOKEN"
    }
