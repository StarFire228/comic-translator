@echo off
chcp 65001 >nul
title Перевод папки комикса
rem Перетащи папку со страницами на этот файл.
rem Перевод появится рядом, в папке "<имя папки> (RU)".
rem Уже переведённые страницы пропускаются, так что после обрыва просто запусти снова.

if "%~1"=="" (
  echo Перетащи папку со страницами комикса на этот файл.
  pause
  exit /b 1
)
if not exist "%~1\" (
  echo Это не папка: %~1
  pause
  exit /b 1
)

set "SRC=%~f1"
set "DEST=%~f1 (RU)"

set CUSTOM_OPENAI_API_BASE=http://127.0.0.1:11434/v1
set CUSTOM_OPENAI_API_KEY=ollama
set CUSTOM_OPENAI_MODEL=gemma3:12b
set VLM_OCR_MODEL=gemma3:12b
set PYTHONUTF8=1
set OLLAMA_MODELS=E:\ComicTranslator\ollama-models

rem Сервер для браузера занимает ту же видеокарту: два сразу не потянут
curl -s http://127.0.0.1:8000 >nul 2>&1 && (
  echo Сейчас запущен переводчик для браузера ^(start.bat^).
  echo Закрой его окно и запусти этот файл снова.
  pause
  exit /b 1
)

curl -s http://127.0.0.1:11434/api/version >nul 2>&1 || start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve

echo Перевожу: %SRC%
echo Результат: %DEST%
echo Около 10 секунд на страницу. Окно не закрывай.
echo.

cd /d E:\ComicTranslator\mit
E:\ComicTranslator\venv\Scripts\python.exe -m manga_translator --use-gpu --ignore-errors --attempts 2 local -i "%SRC%" -o "%DEST%" --config-file E:\ComicTranslator\batch-config.json

echo.
echo Готово. Перевод в папке: %DEST%
pause
