# План проекта: MKV Turbo Pipeline

## 1) Product vision

**Задача:** отправка MKV с Windows 10 на Ubuntu 22.04 VDS, перекодирование с настраиваемым кодеком/параметрами на всех ядрах и быстрая обратная доставка результата.

**KPI MVP (первые 2–3 недели):**
- Время старта задачи после выбора файла: до 10 секунд.
- Успешная обработка файлов 10–50 ГБ с возобновлением после обрыва.
- Детальный прогресс: upload %, transcode %, download %.

## 2) Этапы (Roadmap)

### Этап A — MVP (Неделя 1)
- [ ] Репозиторий + базовая документация.
- [ ] Сервер: FastAPI + endpoint создания задачи.
- [ ] Воркер: запуск ffmpeg по профилю.
- [ ] Клиент CLI: upload → start job → poll status → download.
- [ ] Логи и коды ошибок.

### Этап B — Надежность (Неделя 2)
- [ ] Resume upload/download (rsync/SFTP).
- [ ] Ретраи и тайм-ауты.
- [ ] Ограничения на размер/формат.
- [ ] Graceful cancel.
- [ ] Автоочистка старых артефактов.

### Этап C — GUI и UX (Неделя 3)
- [ ] Windows GUI: drag&drop файла.
- [ ] Профили кодирования (сохранение/редактирование).
- [ ] История задач.
- [ ] Отображение скорости сети, ETA, FPS кодирования.

### Этап D — Production (Неделя 4+)
- [ ] Docker Compose + systemd.
- [ ] Reverse proxy + HTTPS.
- [ ] Prometheus/Grafana мониторинг.
- [ ] Интеграционные тесты и нагрузочный прогон.

## 3) Технические решения

## 3.1 Кодирование
- CPU по умолчанию: `-threads 0`.
- Профили:
  - `h264_fast_delivery` — быстрое кодирование, нормальный размер.
  - `h265_compact` — меньше размер, медленнее.
  - `copy_audio` — без перекодирования аудио при совместимости.

## 3.2 Передача данных
- Базовый канал: SSH/SFTP.
- Для крупных файлов: rsync с resume.
- Проверка целостности: SHA-256 до/после передачи.

## 3.3 Очередь и масштабирование
- Одна очередь для MVP.
- Ограничение одновременно активных транскодов по CPU/RAM.
- В будущем: несколько workers + приоритеты задач.

## 4) Структура GitHub Project (колонки)

1. **Backlog**
2. **Ready**
3. **In Progress**
4. **Review**
5. **Done**

## 5) Начальный backlog (можно копировать в Issues)

### Epic 1: Core backend
1. `server: create FastAPI service skeleton`
2. `server: add /jobs POST and GET endpoints`
3. `worker: run ffmpeg from profile`
4. `worker: parse ffmpeg progress`
5. `storage: persist jobs and logs`

### Epic 2: Data transfer
6. `transfer: implement upload with resume`
7. `transfer: implement download with resume`
8. `transfer: checksum verification`

### Epic 3: Client
9. `client-cli: submit and monitor job`
10. `client-gui: file picker and profile selector`
11. `client-gui: progress bars + ETA`

### Epic 4: Ops
12. `deploy: docker-compose for server+redis+worker`
13. `deploy: systemd units`
14. `ci: lint + tests workflow`

## 6) Definition of Done (DoD)

Задача считается завершенной, если:
- есть код + тест;
- есть логирование ошибок;
- есть обновленная документация;
- выполнена проверка happy path + 1 error path.

## 7) Риски и контрмеры

- **Упор в CPU** → лимит одновременных задач, приоритетная очередь.
- **Обрыв сети на больших файлах** → resume + chunking + checksum.
- **Переполнение диска на VDS** → preflight-проверка свободного места.
- **Неподходящий кодек для устройства** → пресеты совместимости (TV/Web/Mobile).

## 8) Что делать сегодня (первый день)

1. Создать репозиторий и залить этот каркас.
2. Завести 14 issues из backlog.
3. Создать GitHub Project с 5 колонками.
4. Настроить labels: `backend`, `client`, `transfer`, `infra`, `good first issue`.
5. Взять в работу: issue #1, #2, #6.
