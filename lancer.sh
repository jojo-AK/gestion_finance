#!/bin/bash

echo ""
echo " ============================================"
echo "  FINANCE PERSO - Lancement en cours..."
echo " ============================================"
echo ""

# Verifier que Python est installe
if ! command -v python3 &> /dev/null; then
    echo " ERREUR : Python3 n'est pas installe."
    echo " Installer avec : brew install python (Mac) ou sudo apt install python3 (Linux)"
    exit 1
fi

# Installer Flask si pas present
python3 -c "import flask" 2>/dev/null || {
    echo " Installation de Flask..."
    pip3 install flask
}

echo " Demarrage de l'application..."
echo " Ouvrez votre navigateur sur : http://127.0.0.1:5000"
echo ""

# Ouvrir le navigateur selon l'OS
sleep 2 && (
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open http://127.0.0.1:5000
    else
        xdg-open http://127.0.0.1:5000 2>/dev/null || true
    fi
) &

# Lancer l'application
python3 app.py
