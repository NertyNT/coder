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
