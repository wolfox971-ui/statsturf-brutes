# 1. Utilise une image Python légère
FROM python:3.10-slim

# 2. Définit le dossier de travail dans le serveur
WORKDIR /app

# 3. Installe les dépendances système nécessaires pour le job-queue
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. Copie ton fichier requirements.txt
COPY requirements.txt .

# 5. Installe tes bibliothèques (avec ton fameux [job-queue])
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copie tout le reste de ton code dans le serveur
COPY . .

# 7. Crée le dossier pour la base de données (Volume Railway)
RUN mkdir -p /app/data

# 8. Commande pour lancer le bot
CMD ["python", "main.py"]

