# MKV Turbo Pipeline

Готовый каркас проекта для удобной отправки `.mkv` с **Windows 10** на **VDS Ubuntu 22.04**, перекодирования на всех ядрах с заданными параметрами и автоматической загрузки результата обратно максимально быстрым практичным способом.

## Цель

Сделать инструмент «одной кнопкой»:
1. Выбираешь файл на Windows.
2. Выбираешь профиль кодирования (кодек, CRF/битрейт, пресет, аудио, контейнер).
3. Файл уходит на VDS.
4. VDS кодирует через `ffmpeg` на всех ядрах (`-threads 0`).
5. Готовый файл автоматически возвращается на ПК.

## Рекомендованная архитектура

- **Windows Client (GUI + CLI)**
  - Язык: `Python`.
  - GUI: `CustomTkinter` (простой быстрый UI).
  - Функции: выбор файла, выбор профиля, старт задачи, прогресс, история.
- **VDS Agent (Ubuntu 22.04, systemd service)**
  - REST API: `FastAPI`.
  - Очередь задач: `Redis + RQ` (или `Celery` для роста).
  - Кодирование: `ffmpeg` + `ffprobe`.
- **Передача данных**
  - База: `SFTP/SSH` (надежно и безопасно).
  - Для ускорения больших файлов: `rsync` c возобновлением + `zstd` только если вход не сжат.
  - Обратная доставка: тот же канал с поддержкой resume.
- **Хранилище и метаданные**
  - SQLite/PostgreSQL для задач, статусов и логов.
  - Артефакты: `/srv/transcoder/jobs/<job_id>/`.

## Почему это реально быстро

1. `ffmpeg -threads 0` использует все доступные ядра CPU.
2. Выбор кодека/пресета влияет сильнее, чем «магический протокол»:
   - Самый быстрый CPU: `libx264 -preset veryfast/superfast`.
   - Лучше сжатие, медленнее: `libx265`.
3. Передача больших MKV:
   - Стабильная сеть: `rsync --partial --append-verify`.
   - Нестабильная сеть: обязательно resume + chunked upload.

## Минимальный API (MVP)

- `POST /jobs` — создать задачу.
- `GET /jobs/{id}` — статус и прогресс.
- `GET /jobs/{id}/logs` — логи ffmpeg.
- `POST /jobs/{id}/cancel` — остановка.
- `GET /profiles` — профили кодирования.

## Пример профиля кодирования

```yaml
name: h264_balanced
video_codec: libx264
preset: fast
crf: 21
pix_fmt: yuv420p
audio_codec: aac
audio_bitrate: 192k
container: mp4
extra:
  - "-movflags"
  - "+faststart"
```

## Команда ffmpeg (шаблон)

```bash
ffmpeg -y -threads 0 -i input.mkv \
  -c:v libx264 -preset fast -crf 21 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -movflags +faststart output.mp4
```

## Безопасность

- Только ключевая авторизация SSH (без пароля).
- Изоляция задач в отдельных директориях.
- Ограничения на расширения/размер/длительность.
- Проверка входного файла через `ffprobe` до запуска.
- Лимиты API + audit лог.

## Что уже положить в GitHub (рекомендуемая структура)

```text
.
├─ README.md
├─ docs/
│  ├─ PROJECT_PLAN.md
│  ├─ ARCHITECTURE.md
│  └─ API.md
├─ client/
│  ├─ app/               # GUI
│  ├─ cli/               # консольный запуск
│  └─ tests/
├─ server/
│  ├─ app/
│  ├─ workers/
│  ├─ profiles/
│  └─ tests/
├─ deploy/
│  ├─ docker-compose.yml
│  ├─ systemd/
│  └─ nginx/
└─ .github/
   ├─ workflows/ci.yml
   └─ ISSUE_TEMPLATE/
```


## Политика релизов

- **Beta-релизы** публикуются автоматически при пуше тега формата `vX.Y.Z-beta.N`.
- **Stable-релизы** публикуются только вручную через GitHub Actions `Release Stable (Manual)` с вводом версии `X.Y.Z`.
- Версионирование: **SemVer**.

## Следующий шаг

Открой `docs/PROJECT_PLAN.md` — там готовый пошаговый план (MVP → production) с задачами для GitHub Projects.

## Beta 1 клиент (Python)

В репозитории добавлен CLI-клиент `client_beta1.py`.

Что делает beta 1:
1. Отправляет локальный `.mkv` на VDS (SCP).
2. Запускает `ffmpeg` на VDS с профилем из JSON.
3. Скачивает готовый файл обратно.

### Команды установки

#### Windows 10 (клиент)
```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Git.Git
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

Проверка:
```powershell
python --version
git --version
ssh -V
scp -V
```

#### Ubuntu 22.04 (VDS)
```bash
sudo apt update
sudo apt install -y ffmpeg openssh-server rsync python3 python3-venv python3-pip
ffmpeg -version
```

### Быстрый запуск beta 1

```bash
python client_beta1.py D:\\video\\movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --profile profile.beta1.json \
  --output-dir .\\out
```

Тестовый прогон без реального запуска команд:

```bash
python client_beta1.py D:\\video\\movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --profile profile.beta1.json \
  --dry-run
```

## Beta 1 GUI (modern)

Добавлен `client_gui_beta1.py` с современным тёмным интерфейсом (CustomTkinter):
- выбор MKV/профиля/папки вывода;
- блок подключения к серверу (host/user/port/remote base);
- кнопка **Проверить SSH**;
- кнопка **Старт кодирования**;
- live-логи выполнения.

Запуск GUI:

```bash
pip install -r requirements.txt
python client_gui_beta1.py
```

## Авто beta-релиз после изменений

Добавлен workflow `.github/workflows/release-beta-auto.yml`:
- триггер: каждый push в `main` или `work`;
- создаёт тег вида `v0.1.0-beta.<run_number>`;
- публикует GitHub prerelease автоматически.

Для работы нужен встроенный `GITHUB_TOKEN` c `contents: write` (настраивается в repo settings/actions permissions).

## C++ версия (full code) + компиляция

Добавлена полноценная C++ реализация CLI: `src/client_beta1.cpp`.

Возможности:
- аргументы: `input`, `--host`, `--user`, `--profile`, `--port`, `--remote-base`, `--output-dir`, `--dry-run`;
- загрузка/кодирование/скачивание по SSH/SCP;
- чтение JSON профиля (`profile.beta1.json`) без внешних библиотек;
- `ffmpeg -threads 0` на VDS.

### Сборка (Ubuntu / WSL / Linux)

```bash
sudo apt update
sudo apt install -y build-essential cmake ffmpeg openssh-client
cmake -S . -B build
cmake --build build -j
```

### Запуск

```bash
./build/client_beta1_cpp /path/to/movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --profile profile.beta1.json \
  --output-dir ./out
```

Dry-run:

```bash
./build/client_beta1_cpp /path/to/movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --profile profile.beta1.json \
  --dry-run
```


## Обновление политики beta

- Начиная с этой итерации, **все beta-фичи делаем только на Python**.
- Профиль кодирования теперь настраивается прямо в клиенте (CLI/GUI), без обязательного внешнего JSON.
- В GUI добавлена очередь задач и вынесены ключевые параметры ffmpeg, включая video/audio/subtitle maps и extra args.

### Новый запуск Python CLI (без profile.json)

```bash
python client_beta1.py D:\\video\\movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --video-codec libx265 \
  --crf 22 \
  --preset medium \
  --audio-codec aac \
  --audio-bitrate 192k \
  --audio-maps 0:a:0,0:a:1 \
  --subtitle-maps 0:s? \
  --extra-ffmpeg -movflags \
  --extra-ffmpeg +faststart
```

### GUI

```bash
pip install -r requirements.txt
python client_gui_beta1.py
```

Вкладка **FFmpeg** содержит все основные настройки, вкладка **Очередь** — пакетная обработка файлов.

## ffprobe анализ map на локальном ПК

### CLI

Только анализ без отправки на сервер:

```bash
python client_beta1.py D:\\video\\movie.mkv --analyze-only
```

Авто-подстановка map из ffprobe перед кодированием:

```bash
python client_beta1.py D:\\video\\movie.mkv \
  --host 203.0.113.10 \
  --user ubuntu \
  --auto-map-from-ffprobe
```

### GUI

В `client_gui_beta1.py` есть кнопка **Анализировать ffprobe** и чекбокс
**Авто-подстановка map из ffprobe перед запуском**.

## Server Beta 1 (Python)

Добавлен `server_beta1.py` (FastAPI) с максимально простой установкой.

### Установка

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-pip
python3 -m pip install -r requirements-server.txt
```

### Запуск

```bash
uvicorn server_beta1:app --host 0.0.0.0 --port 8080
```

### Эндпоинты

- `GET /health`
- `POST /probe` — ffprobe анализ локального файла на сервере
- `POST /encode` — запуск ffmpeg с параметрами

## Что в релизе

Beta-release workflow теперь всегда прикладывает:
- `client_beta1.py`
- `client_gui_beta1.py`
- `server_beta1.py`
- `python-beta-files.zip`

И добавляет в описание релиза блок "Что добавлено в этом beta-релизе".

## Важно: SSH key / сертификат и запуск клиентов в одной папке

Чтобы не было ошибки с `--profile` (старый скрипт), GUI теперь запускает CLI
строго по пути рядом с собой: `client_gui_beta1.py` -> `client_beta1.py`.

### SSH key/cert

В CLI добавлены:
- `--ssh-key <path_to_private_key>`
- `--ssh-option <OpenSSH_option>` (можно повторять)

Пример:

```bash
python client_beta1.py D:\\video\\movie.mkv \
  --host 192.144.13.118 \
  --user nertyuwu \
  --ssh-key C:\\Users\\NertyUwU\\.ssh\\id_ed25519 \
  --ssh-option StrictHostKeyChecking=accept-new \
  --ssh-option ServerAliveInterval=30 \
  --auto-map-from-ffprobe
```

В GUI добавлены поля `SSH key (private)` и `SSH options (csv)`.

## Server Beta 1 запуск без автозавершения

Теперь `python3 server_beta1.py` поднимает uvicorn автоматически на `:8080`.
Если хочешь вручную, по-прежнему можно:

```bash
uvicorn server_beta1:app --host 0.0.0.0 --port 8080
```

## WinError 2 / "Не удается найти указанный файл"

Это значит, что в PATH нет нужной утилиты (обычно `ssh`, `scp` или `ffprobe`).

### Windows 10/11: поставить OpenSSH Client и ffmpeg

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
winget install -e --id Gyan.FFmpeg
```

Проверка:

```powershell
ssh -V
scp -V
ffprobe -version
```

GUI теперь не падает на таком кейсе и показывает понятную ошибку в окне/логах.

## Авто-установка зависимостей при старте клиента

Добавлен `bootstrap_client.py`. Он при запуске:
1. ставит Python-зависимости из `requirements.txt`;
2. на Windows пытается установить OpenSSH Client и FFmpeg (через `powershell`/`winget`), если их нет;
3. запускает `client_gui_beta1.py`.

Запуск:

```bash
python bootstrap_client.py
```

## Как подключиться к серверу (который уже поднялся на :8080)

Если у тебя в консоли видно:
`Uvicorn running on http://0.0.0.0:8080`, значит сервер слушает все интерфейсы.

### Проверка с локальной машины сервера

```bash
curl http://127.0.0.1:8080/health
```

### Проверка с твоего Windows ПК

```powershell
curl http://192.144.13.118:8080/health
```

### Пример probe-запроса

```powershell
curl -X POST http://192.144.13.118:8080/probe -H "Content-Type: application/json" -d '{"input_path":"/path/to/file.mkv"}'
```

### Важно если не коннектится
- открой порт `8080` в firewall на VDS;
- проверь security group/панель провайдера;
- убедись, что `uvicorn` запущен не только локально и процесс жив.

## Если OpenSSH установлен, но GUI всё равно не видит `ssh`

Новая версия `client_gui_beta1.py` автоматически добавляет
`C:\\Windows\\System32\\OpenSSH` в PATH внутри процесса.

Также очередь теперь оборачивает фоновые ошибки в безопасный лог и не роняет GUI traceback'ом.
