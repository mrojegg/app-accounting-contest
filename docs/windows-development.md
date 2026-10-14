# Windows development

## Статус

- текущий рабочий релиз остается macOS-only
- в репозиторий добавлен Windows scaffolding без изменений текущей macOS сборки
- сейчас есть portable bundle и PyInstaller scaffolding для `.exe`
- сборка самого `.exe` должна выполняться на Windows

## Что уже есть

- `requirements-windows.txt` - базовые Python зависимости для Windows
- `requirements-windows-build.txt` - зависимости для packaging tooling
- `src/windows_app/launcher.py` - отдельный Windows/cross-platform GUI launcher
- `src/windows_app/launcher.spec` - PyInstaller spec для Windows launcher
- `Internal_DO_NOT_DELETE/tools/build_windows_portable.ps1` - сборка portable Windows bundle
- `Internal_DO_NOT_DELETE/tools/package_windows_portable.ps1` - упаковка portable bundle в zip
- `Internal_DO_NOT_DELETE/tools/build_windows_exe.ps1` - сборка Windows `.exe` через PyInstaller
- `Internal_DO_NOT_DELETE/scripts/validate_windows_export.py` - проверка Windows-safe архива

## Внешние инструменты для extraction/OCR

- `tesseract`
- `pdftotext` (Poppler)
- `mutool` (MuPDF)
- `ocrmypdf` опционально
- `ghostscript` нужен для `ocrmypdf`

## Быстрый старт на Windows

```powershell
py -3.11 -m venv .venv-windows
.venv-windows\Scripts\python.exe -m pip install --upgrade pip
.venv-windows\Scripts\python.exe -m pip install -r requirements-windows-build.txt
python -m unittest discover -s Internal_DO_NOT_DELETE/tests -p "test_*.py"
```

## Сборка `.exe`

```powershell
powershell -ExecutionPolicy Bypass -File .\Internal_DO_NOT_DELETE\tools\build_windows_exe.ps1
```

Результат будет в `Dist\windows-exe\SortingFilesWindows\`.

## Сборка portable bundle

```powershell
powershell -ExecutionPolicy Bypass -File .\Internal_DO_NOT_DELETE\tools\build_windows_portable.ps1
powershell -ExecutionPolicy Bypass -File .\Internal_DO_NOT_DELETE\tools\package_windows_portable.ps1
```

Portable bundle по-прежнему не делает `.exe`. Для `.exe` используй PyInstaller script выше.
