"""Переводчик комиксов: окно для перевода папок и управления браузерным переводчиком.

Запуск: ярлык «Переводчик комиксов» (venv\\Scripts\\pythonw.exe app\\comic_translator_app.py).
Сам перевод делает manga-image-translator (папка mit) — приложение лишь запускает его
и показывает прогресс.
"""
import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import psutil
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent          # E:\ComicTranslator
MIT = ROOT / 'mit'
PYTHON = ROOT / 'venv' / 'Scripts' / 'python.exe'
BATCH_CONFIG = ROOT / 'batch-config.json'
OLLAMA_MODELS = ROOT / 'ollama-models'
OLLAMA_EXE = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'ollama.exe'
SETTINGS_FILE = ROOT / 'app-settings.json'
ICON = Path(__file__).resolve().parent / 'icon.ico'

VISION_MODEL = 'gemma3:12b'          # читает текст с картинки (vlm_ocr.py)
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
NO_WINDOW = subprocess.CREATE_NO_WINDOW

MODEL_HINTS = {
    'gemma3:12b': 'лучшее качество',
    'aya-expanse:8b': 'быстрее, проще перевод',
    'qwen3:8b': 'быстрее',
}

# ---------- цвета и шрифты ----------
BG = '#16171d'
PANEL = '#1f2029'
PANEL_2 = '#272834'
TEXT = '#e8e8ef'
MUTED = '#9a9cad'
ACCENT = '#7c5cff'
ACCENT_HOVER = '#6a4be6'
OK = '#3ecf8e'
WARN = '#f5b84b'
BAD = '#ff5d6c'


def font(size=13, weight='normal'):
    return ctk.CTkFont(family='Segoe UI', size=size, weight=weight)


# ---------- утилиты ----------
def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def installed_models() -> list:
    lib = OLLAMA_MODELS / 'manifests' / 'registry.ollama.ai' / 'library'
    models = []
    if lib.is_dir():
        for name in sorted(lib.iterdir()):
            for tag in sorted(name.iterdir()):
                models.append(f'{name.name}:{tag.name}')
    return models or [VISION_MODEL]


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', port)) == 0


def images_in(folder: Path) -> list:
    try:
        return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    except OSError:
        return []


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m = rest // 60
    if h:
        return f'{h} ч {m:02d} мин'
    if m:
        return f'{m} мин'
    return 'меньше минуты'


def translator_env(model: str) -> dict:
    env = os.environ.copy()
    env.update({
        'CUSTOM_OPENAI_API_BASE': 'http://127.0.0.1:11434/v1',
        'CUSTOM_OPENAI_API_KEY': 'ollama',
        'CUSTOM_OPENAI_MODEL': model,
        'VLM_OCR_MODEL': VISION_MODEL,
        'PYTHONUTF8': '1',
        'PYTHONUNBUFFERED': '1',
        'OLLAMA_MODELS': str(OLLAMA_MODELS),
    })
    return env


def ensure_ollama():
    if port_open(11434):
        return
    env = os.environ.copy()
    env['OLLAMA_MODELS'] = str(OLLAMA_MODELS)
    subprocess.Popen([str(OLLAMA_EXE), 'serve'], env=env, creationflags=NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if port_open(11434):
            return
        time.sleep(0.5)


def kill_tree(pid: int):
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for p in proc.children(recursive=True) + [proc]:
        try:
            p.kill()
        except psutil.Error:
            pass


def server_processes() -> list:
    """Процессы браузерного переводчика, в том числе запущенные через start.bat."""
    found = []
    for p in psutil.process_iter(['cmdline']):
        cmd = ' '.join(p.info['cmdline'] or [])
        if 'ComicTranslator' in cmd and ('server\\main.py' in cmd or 'manga_translator shared' in cmd):
            found.append(p)
    return found


def batch_processes() -> list:
    """Перевод папки, запущенный вне этого окна (translate-folder.bat)."""
    found = []
    for p in psutil.process_iter(['cmdline']):
        cmd = p.info['cmdline'] or []
        if 'manga_translator' in cmd and 'local' in cmd:
            found.append(p)
    return found


def gpu_stats():
    try:
        out = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout.strip().splitlines()[0]
        temp, util, used, total, power = [v.strip() for v in out.split(',')]
        return {'temp': int(float(temp)), 'util': int(float(util)), 'used': int(float(used)),
                'total': int(float(total)), 'power': float(power) if power not in ('[N/A]', '') else None}
    except Exception:
        return None


# ---------- окно ----------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('dark')
        self.title('Переводчик комиксов')
        self.minsize(880, 600)
        self._place_window(1000, 660)
        self.configure(fg_color=BG)
        if ICON.exists():
            try:
                self.iconbitmap(str(ICON))
            except Exception:
                pass

        self.settings = load_settings()
        self.models = installed_models()
        self.lines = queue.Queue()
        self.batch = None              # subprocess.Popen перевода папки
        self.paused = False
        self.stop_requested = False
        self.src = None
        self.dest = None
        self.total = 0
        self.done_at_start = 0
        self.started_at = 0.0
        self.paused_time = 0.0
        self.paused_since = 0.0
        self.error_count = 0
        self.preview_path = None
        self.server = None             # subprocess.Popen браузерного переводчика
        self.server_state = 'off'
        self.log_visible = False
        self.gpu = None

        self._build()
        folder = self.settings.get('last_folder')
        if folder and Path(folder).is_dir():
            self._set_folder(Path(folder))

        threading.Thread(target=self._gpu_loop, daemon=True).start()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(300, self._tick)

    def _place_window(self, w, h):
        """По центру экрана и не больше его (с учётом масштабирования Windows и панели задач)."""
        self.update_idletasks()
        scale = self._get_window_scaling()
        sw, sh = self.winfo_screenwidth() / scale, self.winfo_screenheight() / scale
        w, h = min(w, int(sw - 40)), min(h, int(sh - 90))
        x, y = int((sw - w) / 2), max(int((sh - h) / 2) - 30, 0)
        self.geometry(f'{w}x{h}+{int(x * scale)}+{int(y * scale)}')

    # ----- разметка -----
    def _build(self):
        # uniform: пропорции колонок не зависят от размера превью
        self.grid_columnconfigure(0, weight=3, uniform='cols')
        self.grid_columnconfigure(1, weight=2, uniform='cols')
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text='Переводчик комиксов', font=font(24, 'bold'), text_color=TEXT).pack(side='left')
        ctk.CTkLabel(header, text='  английский → русский, всё локально', font=font(13), text_color=MUTED).pack(side='left', pady=(6, 0))

        # левая колонка: перевод папки
        left = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        left.grid(row=1, column=0, sticky='nsew', padx=(24, 10), pady=(8, 24))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(left, text='Перевод папки', font=font(16, 'bold'), text_color=TEXT).grid(
            row=0, column=0, sticky='w', padx=20, pady=(18, 10))

        pick = ctk.CTkFrame(left, fg_color=PANEL_2, corner_radius=10)
        pick.grid(row=1, column=0, sticky='ew', padx=20)
        pick.grid_columnconfigure(0, weight=1)
        self.folder_label = ctk.CTkLabel(pick, text='Папка не выбрана', font=font(13), text_color=MUTED,
                                         anchor='w', justify='left', wraplength=330)
        self.folder_label.grid(row=0, column=0, sticky='ew', padx=14, pady=(12, 2))
        self.folder_info = ctk.CTkLabel(pick, text='Выбери папку со страницами комикса', font=font(12),
                                        text_color=MUTED, anchor='w')
        self.folder_info.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 12))
        self.pick_btn = ctk.CTkButton(pick, text='Выбрать папку', width=140, height=36, font=font(13, 'bold'),
                                      fg_color=PANEL, hover_color='#33354a', border_width=1, border_color='#3a3c50',
                                      command=self._pick_folder)
        self.pick_btn.grid(row=0, column=1, rowspan=2, padx=12)

        opts = ctk.CTkFrame(left, fg_color='transparent')
        opts.grid(row=2, column=0, sticky='ew', padx=20, pady=(14, 0))
        ctk.CTkLabel(opts, text='Модель перевода', font=font(13), text_color=MUTED).pack(side='left')
        model = self.settings.get('model', VISION_MODEL)
        if model not in self.models:
            model = self.models[0]
        self.model_var = ctk.StringVar(value=model)
        self.model_menu = ctk.CTkOptionMenu(opts, values=self.models, variable=self.model_var, width=170,
                                            font=font(13), fg_color=PANEL_2, button_color=PANEL_2,
                                            button_hover_color='#33354a', dropdown_fg_color=PANEL_2,
                                            command=self._model_changed)
        self.model_menu.pack(side='left', padx=10)
        self.model_hint = ctk.CTkLabel(opts, text='', font=font(12), text_color=MUTED)
        self.model_hint.pack(side='left')
        self._model_changed(model)

        controls = ctk.CTkFrame(left, fg_color='transparent')
        controls.grid(row=3, column=0, sticky='ew', padx=20, pady=(16, 0))
        self.start_btn = ctk.CTkButton(controls, text='▶  Перевести', height=44, width=180, font=font(15, 'bold'),
                                       fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._start)
        self.start_btn.pack(side='left')
        self.pause_btn = ctk.CTkButton(controls, text='⏸  Пауза', height=44, width=120, font=font(14),
                                       fg_color=PANEL_2, hover_color='#33354a', command=self._toggle_pause,
                                       state='disabled')
        self.pause_btn.pack(side='left', padx=10)
        self.stop_btn = ctk.CTkButton(controls, text='■  Стоп', height=44, width=110, font=font(14),
                                      fg_color=PANEL_2, hover_color='#4a2a30', command=self._stop,
                                      state='disabled')
        self.stop_btn.pack(side='left')

        prog = ctk.CTkFrame(left, fg_color='transparent')
        prog.grid(row=4, column=0, sticky='ew', padx=20, pady=(18, 0))
        prog.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(prog, text='Готов к работе', font=font(14, 'bold'), text_color=TEXT, anchor='w')
        self.status.grid(row=0, column=0, sticky='ew')
        self.progress = ctk.CTkProgressBar(prog, height=12, corner_radius=6, progress_color=ACCENT, fg_color=PANEL_2)
        self.progress.grid(row=1, column=0, sticky='ew', pady=8)
        self.progress.set(0)
        self.progress_info = ctk.CTkLabel(prog, text='', font=font(12), text_color=MUTED, anchor='w')
        self.progress_info.grid(row=2, column=0, sticky='ew')

        bottom = ctk.CTkFrame(left, fg_color='transparent')
        bottom.grid(row=5, column=0, sticky='nsew', padx=20, pady=(10, 16))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_rowconfigure(1, weight=1)
        btns = ctk.CTkFrame(bottom, fg_color='transparent')
        btns.grid(row=0, column=0, sticky='ew')
        self.open_btn = ctk.CTkButton(btns, text='Открыть папку с переводом', height=32, font=font(13),
                                      fg_color=PANEL_2, hover_color='#33354a', command=self._open_dest,
                                      state='disabled')
        self.open_btn.pack(side='left')
        self.log_btn = ctk.CTkButton(btns, text='Подробности ▾', height=32, width=130, font=font(13),
                                     fg_color='transparent', hover_color=PANEL_2, text_color=MUTED,
                                     command=self._toggle_log)
        self.log_btn.pack(side='right')
        self.log = ctk.CTkTextbox(bottom, font=ctk.CTkFont(family='Consolas', size=11), fg_color='#121318',
                                  text_color='#b9bbcc', corner_radius=8, wrap='none')
        self.log.configure(state='disabled')

        # правая колонка: превью, видеокарта, браузер
        right = ctk.CTkFrame(self, fg_color='transparent')
        right.grid(row=1, column=1, sticky='nsew', padx=(10, 24), pady=(8, 24))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        prev = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=14)
        prev.grid(row=0, column=0, sticky='nsew')
        prev.grid_columnconfigure(0, weight=1)
        prev.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(prev, text='Последняя переведённая страница', font=font(13, 'bold'), text_color=TEXT).grid(
            row=0, column=0, sticky='w', padx=16, pady=(14, 6))
        self.preview = ctk.CTkLabel(prev, text='Здесь появится превью', font=font(12), text_color=MUTED)
        self.preview.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 16))
        self.preview.bind('<Configure>', lambda e: self._refresh_preview(force=True))

        gpu = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=14)
        gpu.grid(row=1, column=0, sticky='ew', pady=(12, 0))
        gpu.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(gpu, text='Видеокарта', font=font(13, 'bold'), text_color=TEXT).grid(
            row=0, column=0, columnspan=3, sticky='w', padx=16, pady=(12, 4))
        self.gpu_temp = self._stat(gpu, 0, 'Температура')
        self.gpu_load = self._stat(gpu, 1, 'Загрузка')
        self.gpu_mem = self._stat(gpu, 2, 'Видеопамять')
        self.gpu_note = ctk.CTkLabel(gpu, text='', font=font(11), text_color=MUTED, anchor='w')
        self.gpu_note.grid(row=3, column=0, columnspan=3, sticky='ew', padx=16, pady=(0, 10))

        srv = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=14)
        srv.grid(row=2, column=0, sticky='ew', pady=(12, 0))
        srv.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(srv, text='Перевод в браузере (Alt+T)', font=font(13, 'bold'), text_color=TEXT).grid(
            row=0, column=0, sticky='w', padx=16, pady=(12, 0))
        self.server_label = ctk.CTkLabel(srv, text='Выключен', font=font(12), text_color=MUTED, anchor='w')
        self.server_label.grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 12))
        self.server_btn = ctk.CTkButton(srv, text='Включить', width=110, height=34, font=font(13, 'bold'),
                                        fg_color=PANEL_2, hover_color='#33354a', command=self._toggle_server)
        self.server_btn.grid(row=0, column=1, rowspan=2, padx=14)

    def _stat(self, parent, col, title):
        ctk.CTkLabel(parent, text=title, font=font(11), text_color=MUTED).grid(row=1, column=col, padx=16, sticky='w')
        value = ctk.CTkLabel(parent, text='—', font=font(20, 'bold'), text_color=TEXT)
        value.grid(row=2, column=col, padx=16, sticky='w', pady=(0, 4))
        return value

    # ----- выбор папки -----
    def _pick_folder(self):
        start = self.settings.get('last_folder') or str(Path.home())
        folder = filedialog.askdirectory(title='Папка со страницами комикса', initialdir=start)
        if folder:
            self._set_folder(Path(folder))

    def _set_folder(self, folder: Path):
        self.src = folder
        self.dest = folder.with_name(folder.name + ' (RU)')
        imgs = images_in(folder)
        self.total = len(imgs)
        done = self._count_done()
        name = folder.name if len(folder.name) <= 48 else folder.name[:45] + '…'
        self.folder_label.configure(text=name, text_color=TEXT, font=font(14, 'bold'))
        if not imgs:
            self.folder_info.configure(text='Нет картинок. Если это zip — сначала распакуй', text_color=WARN)
        elif done:
            self.folder_info.configure(text=f'Страниц: {self.total}  ·  уже переведено: {done}', text_color=MUTED)
        else:
            self.folder_info.configure(text=f'Страниц: {self.total}', text_color=MUTED)
        self.progress.set(done / self.total if self.total else 0)
        self.progress_info.configure(text=f'{done} из {self.total}' if self.total else '')
        self.open_btn.configure(state='normal' if self.dest.exists() else 'disabled')
        self.settings['last_folder'] = str(folder)
        save_settings(self.settings)
        self.preview_path = None
        self._refresh_preview()

    def _count_done(self) -> int:
        if not self.src or not self.dest or not self.dest.is_dir():
            return 0
        names = {p.name for p in self.dest.iterdir()}
        return sum(1 for p in images_in(self.src) if p.name in names)

    def _model_changed(self, value):
        self.model_hint.configure(text=MODEL_HINTS.get(value, ''))
        self.settings['model'] = value
        save_settings(self.settings)

    # ----- перевод -----
    def _start(self):
        if self.batch:
            return
        if not self.src or not self.total:
            messagebox.showinfo('Переводчик комиксов', 'Сначала выбери папку со страницами комикса.')
            return
        if self._count_done() >= self.total:
            messagebox.showinfo('Переводчик комиксов', 'Вся папка уже переведена.')
            return
        if batch_processes():
            messagebox.showwarning('Переводчик комиксов',
                                   'Уже идёт перевод другой папки (через translate-folder.bat).\n\n'
                                   'Дождись его окончания или закрой его окно.')
            return
        if server_processes() or port_open(8000):
            if not messagebox.askyesno('Переводчик комиксов',
                                       'Сейчас включён перевод в браузере, вдвоём они не помещаются в видеопамять.\n\n'
                                       'Выключить его и начать перевод папки?'):
                return
            self._stop_server()

        self.stop_requested = False
        self.paused = False
        self.paused_time = 0.0
        self.error_count = 0
        self.done_at_start = self._count_done()
        self.started_at = time.time()
        self._log_clear()
        self._set_running(True)
        self.status.configure(text='Запускаю…', text_color=TEXT)
        threading.Thread(target=self._run_batch, daemon=True).start()

    def _run_batch(self):
        self.lines.put(('status', 'Запускаю Ollama…'))
        ensure_ollama()
        self.lines.put(('status', 'Загружаю модели (около минуты)…'))
        cmd = [str(PYTHON), '-m', 'manga_translator', '--use-gpu', '--ignore-errors', '--attempts', '2',
               'local', '-i', str(self.src), '-o', str(self.dest), '--config-file', str(BATCH_CONFIG)]
        try:
            self.batch = subprocess.Popen(cmd, cwd=str(MIT), env=translator_env(self.model_var.get()),
                                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                          creationflags=NO_WINDOW, text=True, encoding='utf-8', errors='replace',
                                          bufsize=1)
        except Exception as e:
            self.lines.put(('finished', f'Не удалось запустить переводчик: {e}'))
            return
        buf = ''
        while True:
            ch = self.batch.stdout.read(1)
            if not ch:
                break
            if ch in '\r\n':
                if buf.strip():
                    self.lines.put(('line', buf))
                buf = ''
            else:
                buf += ch
        code = self.batch.wait()
        self.lines.put(('finished', code))

    def _toggle_pause(self):
        if not self.batch:
            return
        try:
            proc = psutil.Process(self.batch.pid)
            targets = [proc] + proc.children(recursive=True)
            if self.paused:
                for p in targets:
                    p.resume()
                self.paused = False
                self.paused_time += time.time() - self.paused_since
                self.pause_btn.configure(text='⏸  Пауза')
                self.status.configure(text='Продолжаю перевод…', text_color=TEXT)
            else:
                for p in targets:
                    p.suspend()
                self.paused = True
                self.paused_since = time.time()
                self.pause_btn.configure(text='▶  Продолжить')
                self.status.configure(text='На паузе', text_color=WARN)
        except psutil.Error as e:
            self._log(f'Пауза не удалась: {e}')

    def _stop(self):
        if not self.batch:
            return
        if not messagebox.askyesno('Переводчик комиксов',
                                   'Остановить перевод?\n\nГотовые страницы сохранятся, потом можно продолжить с того же места.'):
            return
        self.stop_requested = True
        if self.paused:
            self._toggle_pause()
        kill_tree(self.batch.pid)

    def _set_running(self, running: bool):
        self.start_btn.configure(state='disabled' if running else 'normal')
        self.pick_btn.configure(state='disabled' if running else 'normal')
        self.model_menu.configure(state='disabled' if running else 'normal')
        self.pause_btn.configure(state='normal' if running else 'disabled', text='⏸  Пауза')
        self.stop_btn.configure(state='normal' if running else 'disabled')
        self.server_btn.configure(state='disabled' if running else 'normal')

    def _handle_line(self, line: str):
        self._log(line)
        m = re.search(r'\[local\] Translating: "(.+)"', line)
        if m:
            self.status.configure(text=f'Перевожу: {Path(m.group(1)).name}', text_color=TEXT)
        if line.startswith('ERROR') or 'Traceback' in line:
            self.error_count += 1

    def _finished(self, code):
        batch_done = self._count_done()
        self.batch = None
        self.paused = False
        self._set_running(False)
        self._update_progress()
        self.open_btn.configure(state='normal' if self.dest and self.dest.exists() else 'disabled')
        if isinstance(code, str):
            self.status.configure(text=code, text_color=BAD)
        elif self.stop_requested:
            self.status.configure(text=f'Остановлено. Переведено {batch_done} из {self.total}', text_color=WARN)
        elif code == 0 and batch_done >= self.total:
            self.status.configure(text='Готово! Весь комикс переведён', text_color=OK)
            self.bell()
        elif code == 0:
            self.status.configure(text=f'Готово, но {self.total - batch_done} стр. не удалось перевести — '
                                       f'нажми «Перевести» ещё раз', text_color=WARN)
        else:
            self.status.configure(text='Перевод прервался с ошибкой — см. «Подробности». '
                                       'Готовые страницы сохранены', text_color=BAD)
            if not self.log_visible:
                self._toggle_log()

    def _update_progress(self):
        if not self.total:
            return
        done = self._count_done()
        self.progress.set(done / self.total)
        info = f'{done} из {self.total}'
        if self.batch:
            new = done - self.done_at_start
            elapsed = time.time() - self.started_at - self.paused_time
            if self.paused:
                elapsed -= time.time() - self.paused_since
            if new > 0:
                per_page = elapsed / new
                info += f'   ·   ~{per_page:.0f} с на страницу   ·   осталось {fmt_duration(per_page * (self.total - done))}'
            if self.error_count:
                info += f'   ·   ошибок: {self.error_count}'
        self.progress_info.configure(text=info)

    # ----- превью -----
    def _refresh_preview(self, force=False):
        if not self.dest or not self.dest.is_dir():
            if force or self.preview_path is not None:
                self.preview.configure(image=None, text='Здесь появится превью')
                self.preview_path = None
            return
        files = [p for p in self.dest.iterdir() if p.suffix.lower() in IMAGE_EXTS]
        if not files:
            return
        newest = max(files, key=lambda p: p.stat().st_mtime)
        if newest == self.preview_path and not force:
            return
        try:
            img = Image.open(newest)
            img.load()
        except Exception:
            return  # файл ещё дописывается
        box_w = max(self.preview.winfo_width() - 8, 200)
        box_h = max(self.preview.winfo_height() - 8, 200)
        scale = min(box_w / img.width, box_h / img.height, 1.0)
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        self._preview_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.preview.configure(image=self._preview_img, text='')
        self.preview_path = newest

    def _open_dest(self):
        if self.dest and self.dest.exists():
            os.startfile(self.dest)

    # ----- подробности -----
    def _toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log.grid(row=1, column=0, sticky='nsew', pady=(8, 0))
            self.log_btn.configure(text='Подробности ▴')
        else:
            self.log.grid_forget()
            self.log_btn.configure(text='Подробности ▾')

    def _log(self, text: str):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        if int(self.log.index('end-1c').split('.')[0]) > 2000:
            self.log.delete('1.0', '500.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _log_clear(self):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    # ----- браузерный переводчик -----
    def _toggle_server(self):
        if self.server_state in ('on', 'starting'):
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self):
        self.server_state = 'starting'
        self._update_server_ui()

        def run():
            ensure_ollama()
            cmd = [str(PYTHON), 'server/main.py', '--use-gpu', '--start-instance', '--nonce', 'None',
                   '--host', '127.0.0.1', '--port', '8000']
            self.server = subprocess.Popen(cmd, cwd=str(MIT), env=translator_env(self.model_var.get()),
                                           creationflags=NO_WINDOW, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
        threading.Thread(target=run, daemon=True).start()

    def _stop_server(self):
        if self.server:
            kill_tree(self.server.pid)
            self.server = None
        for p in server_processes():
            kill_tree(p.pid)
        self.server_state = 'off'
        self._update_server_ui()

    def _check_server(self):
        ready = port_open(8001) and port_open(8000)
        if self.server_state == 'starting':
            if ready:
                self.server_state = 'on'
            elif self.server and self.server.poll() is not None:
                self.server_state = 'off'
                self.server = None
                messagebox.showerror('Переводчик комиксов', 'Браузерный переводчик не запустился.')
        elif self.server_state == 'off' and ready:
            self.server_state = 'on'       # запущен снаружи, например через start.bat
        elif self.server_state == 'on' and not ready:
            self.server_state = 'off'
        self._update_server_ui()

    def _update_server_ui(self):
        if self.server_state == 'on':
            self.server_label.configure(text='● Работает — открой страницу и нажми Alt+T', text_color=OK)
            self.server_btn.configure(text='Выключить')
        elif self.server_state == 'starting':
            self.server_label.configure(text='● Запускается, около минуты…', text_color=WARN)
            self.server_btn.configure(text='Отмена')
        else:
            self.server_label.configure(text='Выключен', text_color=MUTED)
            self.server_btn.configure(text='Включить')

    # ----- видеокарта -----
    def _gpu_loop(self):
        while True:
            self.gpu = gpu_stats()
            time.sleep(2)

    def _update_gpu(self):
        g = self.gpu
        if not g:
            self.gpu_note.configure(text='Нет данных от nvidia-smi')
            return
        t = g['temp']
        self.gpu_temp.configure(text=f'{t} °C', text_color=OK if t < 75 else WARN if t < 84 else BAD)
        self.gpu_load.configure(text=f'{g["util"]} %')
        self.gpu_mem.configure(text=f'{g["used"] / 1024:.1f} / {g["total"] / 1024:.0f} ГБ')
        note = f'Потребление {g["power"]:.0f} Вт' if g['power'] else ''
        if t >= 84:
            note += ('   ·   ' if note else '') + 'Горячо: проверь обдув корпуса'
        self.gpu_note.configure(text=note, text_color=BAD if t >= 84 else MUTED)

    # ----- главный цикл -----
    def _tick(self):
        try:
            while True:
                kind, payload = self.lines.get_nowait()
                if kind == 'line':
                    self._handle_line(payload)
                elif kind == 'status':
                    self.status.configure(text=payload, text_color=TEXT)
                elif kind == 'finished':
                    self._finished(payload)
        except queue.Empty:
            pass

        now = time.time()
        if now - getattr(self, '_last_slow', 0) > 1.5:
            self._last_slow = now
            if self.batch or self.total:
                self._update_progress()
            if self.batch:
                self._refresh_preview()
            self._update_gpu()
            self._check_server()
        self.after(200, self._tick)

    def _on_close(self):
        if self.batch:
            if not messagebox.askyesno('Переводчик комиксов',
                                       'Идёт перевод. Закрыть окно и остановить его?\n\n'
                                       'Готовые страницы сохранятся, потом можно продолжить.'):
                return
            if self.paused:
                self._toggle_pause()
            kill_tree(self.batch.pid)
        if self.server_state != 'off':
            self._stop_server()
        self.destroy()


if __name__ == '__main__':
    app = App()
    shot = os.environ.get('APP_SCREENSHOT')   # для проверки: снимок окна и выход
    if shot:
        def _shot():
            from PIL import ImageGrab
            app.update()
            x, y = app.winfo_rootx(), app.winfo_rooty()
            ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height())).save(shot)
            app.destroy()
        app.attributes('-topmost', True)
        app.after(int(os.environ.get('APP_SCREENSHOT_DELAY', '3500')), _shot)
    app.mainloop()
