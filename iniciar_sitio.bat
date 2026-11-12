@echo off
rem Sirve la carpeta web y la publica en internet con ngrok. Cierre esta ventana para detenerla.
cd /d "%~dp0"
start "Servidor local" /min python -m http.server 8000 --directory web --bind 127.0.0.1
echo Sitio local: http://localhost:8000
echo Sitio publico: https://debrief-smartly-taco.ngrok-free.dev
ngrok http 8000
