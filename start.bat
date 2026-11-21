@echo off
title Переводчик комиксов
cd /d E:\ComicTranslator\mit

rem Нейросеть для перевода (локально через Ollama)
set CUSTOM_OPENAI_API_BASE=http://127.0.0.1:11434/v1
set CUSTOM_OPENAI_API_KEY=ollama
set CUSTOM_OPENAI_MODEL=gemma3:12b
set PYTHONUTF8=1
set OLLAMA_MODELS=E:\ComicTranslator\ollama-models

rem Поднять Ollama, если она не запущена
curl -s http://127.0.0.1:11434/api/version >nul 2>&1 || start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve

echo Сервер переводчика запускается на http://127.0.0.1:8000
echo Готов, когда появится строка "Uvicorn running on http://127.0.0.1:8001"
echo Не закрывай это окно, пока читаешь. Перевод в браузере: Alt+T
echo.
E:\ComicTranslator\venv\Scripts\python.exe server\main.py --use-gpu --start-instance --nonce None --host 127.0.0.1 --port 8000
pause