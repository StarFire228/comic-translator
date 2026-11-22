@echo off
chcp 65001 >nul
title Перевод папки комикса
rem Перетащи папку со страницами на этот файл.
rem Перевод появится рядом, в папке "<имя папки> (RU)".
rem Уже переведённые страницы пропускаются, так что после обрыва просто запусти снова.
rem Пути выводятся только в кавычках и не подставляются внутрь блоков ( ):
rem иначе скобки и & в названиях галерей ломают разбор батника.

if "%~1"=="" goto :no_arg
if not exist "%~f1\" goto :not_folder

set "SRC=%~f1"
set "DEST=%~f1 (RU)"

set CUSTOM_OPENAI_API_BASE=http://127.0.0.1:11434/v1
set CUSTOM_OPENAI_API_KEY=ollama
set CUSTOM_OPENAI_MODEL=gemma3:12b
set VLM_OCR_MODEL=gemma3:12b
set PYTHONUTF8=1
set OLLAMA_MODELS=E:\ComicTranslator\ollama-models

rem Сервер для браузера занимает ту же видеокарту: два сразу не потянут
curl -s http://127.0.0.1:8000 >nul 2>&1 && goto :server_running

curl -s http://127.0.0.1:11434/api/version >nul 2>&1 || start "" /min "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve

echo Перевожу: "%SRC%"
echo Результат: "%DEST%"
echo Около 30 секунд на страницу. Окно не закрывай.
echo.

cd /d E:\ComicTranslator\mit
E:\ComicTranslator\venv\Scripts\python.exe -m manga_translator --use-gpu --ignore-errors --attempts 2 local -i "%SRC%" -o "%DEST%" --config-file E:\ComicTranslator\batch-config.json
if errorlevel 1 goto :failed

echo.
echo Готово. Перевод в папке: "%DEST%"
pause
exit /b 0

:failed
echo.
echo Перевод прервался с ошибкой, текст ошибки выше.
echo Готовые страницы сохранены: запусти батник ещё раз, и он продолжит.
pause
exit /b 1

:no_arg
echo Перетащи папку со страницами комикса на этот файл.
pause
exit /b 1

:not_folder
echo Это не папка: "%~1"
echo Если это zip-архив, сначала распакуй его в папку.
pause
exit /b 1

:server_running
echo Сейчас запущен переводчик для браузера (start.bat).
echo Закрой его окно и запусти этот файл снова.
pause
exit /b 1
