# Архитектура и сборка

## Компоненты

Нативный интерфейс SwiftUI управляет операциями и локальными правилами. PDFKit обеспечивает просмотр, разбиение и объединение PDF. Локальный Python pipeline извлекает текст, классифицирует документы, обрабатывает ручные решения и формирует Excel и архивы. Нативный helper на основе Apple Vision выполняет OCR слабого текстового слоя и сканов с ограниченным числом повторных попыток.

Состояние обработки включает очередь ручной проверки, подтвержденные поля конкретных файлов и реестр входных документов с контрольными суммами. Финализация формирует таблицы, объединенные чеки, папку исходников, отчет и ZIP. Встроенный Python отделен от Python системы пользователя.

## Каталоги

- `Internal_DO_NOT_DELETE/app_source/native_app`: SwiftUI, PDFKit и тесты интерфейсных моделей.
- `Internal_DO_NOT_DELETE/ocr/ocr_package`: Apple Vision OCR helper.
- `Internal_DO_NOT_DELETE/scripts`: Python-обработчики и финализация.
- `Internal_DO_NOT_DELETE/project_rules`: чистые шаблоны и общие правила распознавания.
- `Internal_DO_NOT_DELETE/tests`: синтетические регрессионные проверки.
- `demo`: вымышленная конфигурация демонстрации.
- `docs/competition`: пользовательская и конкурсная документация.

Исторические специализированные обработчики сохранены для регрессионной совместимости на обезличенных тестовых данных. Настройки нового пользователя определяют реальные компании, офисы и сотрудников.

## Сборка на Mac

Требуются Xcode или Command Line Tools, Swift и переносимый CPython подходящей архитектуры. Python не должен быть ссылкой на системную установку или виртуальным окружением. Текущий проверяемый дистрибутив предназначен для Apple Silicon; Intel требует отдельной сборки и приемки.

```bash
export SORTING_PYTHON_HOME='/absolute/path/to/standalone-python'
"$SORTING_PYTHON_HOME/bin/python3" -m pip install --target Build/python-runtime-deps -r requirements-macos.txt
cd Internal_DO_NOT_DELETE/app_source/native_app
APP_VERSION=1.2.0 zsh ./build_app.sh
cd ../../..
zsh Internal_DO_NOT_DELETE/tools/package_dmg.sh
```

На текущем Xcode сборка использует нативный режим SwiftPM. Этот режим помечен SwiftPM как устаревающий; при обновлении инструментов нужно повторить сборку и тесты. Собранный `.app` и `.dmg` не хранятся в исходниках Git, они публикуются как файлы релиза.

## Тесты

```bash
export SORTING_RULES_FILE="$PWD/Internal_DO_NOT_DELETE/tests/fixtures/ci_sorting_rules.md"
export SORTING_PATTERNS_FILE="$PWD/Internal_DO_NOT_DELETE/tests/fixtures/ci_classification_patterns.json"
python3 -m pip install -r requirements-test.txt
python3 -m unittest discover -s Internal_DO_NOT_DELETE/tests -p 'test_*.py'
swift test --disable-sandbox --build-system native \
  --package-path Internal_DO_NOT_DELETE/app_source/native_app --scratch-path Build/native-tests
```

Для полной проверки OCR и PDF helpers задайте `SORTING_TEST_OCR`, `SORTING_TEST_SCRIPTS` и `SORTING_PDF_MERGER` путями к собранным обработчикам. Проверяйте отчет о пропусках: отсутствие helper не равно успешной проверке OCR.

## Изоляция данных

Bundle identifier конкурсной версии: `local.codex.sortingfiles.contest`. Настройки и кэш используют `SortingFilesContestApp`. Рабочая версия использует другое хранилище. Чистый репозиторий создается без истории личного проекта; файлы личных правил, платежные документы, логи запусков и резервные копии не включаются.

Данные результата не являются анонимными: отчет, Excel и исходники сохраняют сведения выбранных пользователем документов. Эти папки не следует добавлять в Git.
