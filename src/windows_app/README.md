# Windows launcher

New launcher for the existing Python sorting pipeline.

## Run

```bash
python3 src/windows_app/launcher.py
```

If `PySide6` is installed, the launcher uses it. Otherwise it falls back to `tkinter`.

## What it does

- picks source folder
- picks output folder
- sets archive name
- chooses `copy` or `move`
- runs `Internal_DO_NOT_DELETE/scripts/run_sorting_pipeline.py`
- streams logs and phase status

## Notes

- existing macOS Swift app is untouched
- launcher lives separately and uses the current Python engine as-is
