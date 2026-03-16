@echo off
title Finance Perso
echo.
echo  ============================================
echo   FINANCE PERSO - Lancement en cours...
echo  ============================================
echo.

:: Verifier que Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERREUR : Python n'est pas installe.
    echo  Telecharger sur https://www.python.org
    pause
    exit /b
)

:: Installer Flask si pas present
pip show flask >nul 2>&1
if errorlevel 1 (
    echo  Installation de Flask...
    pip install flask
)

echo  Demarrage de l'application...
echo  Ouvrez votre navigateur sur : http://127.0.0.1:5000
echo.

:: Ouvrir le navigateur apres 2 secondes
start /b cmd /c "timeout /t 2 >nul && start http://127.0.0.1:5000"

:: Lancer l'application
python app.py

pause
