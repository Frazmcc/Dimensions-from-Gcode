# G-code Dimensioner

A tiny Flask app that accepts a `.gcode` (or `.gcode.gz`) upload and reports the model's X/Y/Z bounding box by scanning motion commands.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py  # http://localhost:8000
```

## Deploy to Render

1. Create a new **Web Service** from your GitHub repo.
2. Environment: **Python**  
   Build: `pip install -r requirements.txt`  
   Start: `gunicorn app:app --bind 0.0.0.0:8000 --workers 2`
3. Or push with `render.yaml` and choose **Blueprint** deploy.

No publish directory is needed (this is not a static site).

## API

`POST /api/analyze` with form field `file`.

**Response**
```json
{
  "ok": true,
  "line_count": 123456,
  "move_count": 7890,
  "result": {
    "x_min": 10.0, "x_max": 110.0, "x_size": 100.0,
    "y_min": 5.0,  "y_max": 55.0,  "y_size": 50.0,
    "z_min": 0.2,  "z_max": 12.6,  "z_size": 12.4
  }
}
```

## Notes

- Handles both **absolute (G90)** and **relative (G91)** moves by tracking current position.
- Ignores extrusion (`E`) and feedrate (`F`).
- Strips `;` and `( … )` comments to keep parsing robust.
- Streams the file line-by-line, so huge G-code files are fine.
