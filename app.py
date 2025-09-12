from flask import Flask, request, render_template, jsonify, redirect, url_for
import io, gzip, re

app = Flask(__name__)

MOVE_CMDS = ("G0", "G00", "G1", "G01")
ABSOLUTE_CMD = ("G90",)     # absolute positioning for axes
RELATIVE_CMD = ("G91",)     # relative positioning for axes

# Some slicers emit modal G90/G91 for extruder specifically via M82/M83; we ignore E anyway.
COORD_RE = re.compile(r'([XYZ])([-+]?\d*\.?\d+)')

def iter_lines(fileobj, filename: str):
    """
    Yield lines from uploaded file. Supports .gcode and .gcode.gz
    """
    lower = filename.lower()
    if lower.endswith(".gz") or lower.endswith(".gcode.gz"):
        with gzip.GzipFile(fileobj=fileobj, mode="rb") as gz:
            for raw in gz:
                yield raw.decode('utf-8', errors='ignore')
    else:
        for raw in fileobj:
            if isinstance(raw, bytes):
                yield raw.decode('utf-8', errors='ignore')
            else:
                yield raw

def analyze_gcode(file_storage):
    xmin = ymin = zmin = float("inf")
    xmax = ymax = zmax = float("-inf")

    # Track modal state
    absolute = True   # default is usually absolute (G90)
    cur_x = cur_y = cur_z = None

    # Some printers/slicers prefix with comments containing object size; we still compute precisely.
    line_count = 0
    move_count = 0

    for line in iter_lines(file_storage.stream, file_storage.filename):
        line_count += 1

        # Strip comments (after ';' or inside parentheses), keep the command part only
        # Remove ( ... ) comments
        while True:
            start = line.find('(')
            if start == -1:
                break
            end = line.find(')', start + 1)
            if end == -1:
                break
            line = line[:start] + line[end+1:]
        # Remove ; comments
        if ';' in line:
            line = line.split(';', 1)[0]

        line = line.strip()
        if not line:
            continue

        # Modal changes
        up = line.upper()
        if up.startswith(ABSOLUTE_CMD):
            absolute = True
            continue
        if up.startswith(RELATIVE_CMD):
            absolute = False
            continue

        # Consider only motion commands
        parts = up.split()
        if not parts:
            continue
        cmd = parts[0]

        if cmd not in MOVE_CMDS:
            continue

        # Extract any X/Y/Z on this line
        coords = dict(COORD_RE.findall(up))
        if not coords:
            continue

        move_count += 1

        # Update current position according to absolute/relative
        if absolute:
            if 'X' in coords:
                cur_x = float(coords['X'])
            if 'Y' in coords:
                cur_y = float(coords['Y'])
            if 'Z' in coords:
                cur_z = float(coords['Z'])
        else:
            # If relative and coord present, add to current (if current is None, assume 0)
            if 'X' in coords:
                cur_x = (0.0 if cur_x is None else cur_x) + float(coords['X'])
            if 'Y' in coords:
                cur_y = (0.0 if cur_y is None else cur_y) + float(coords['Y'])
            if 'Z' in coords:
                cur_z = (0.0 if cur_z is None else cur_z) + float(coords['Z'])

        # Update bounds with any known current values
        if cur_x is not None:
            xmin = min(xmin, cur_x)
            xmax = max(xmax, cur_x)
        if cur_y is not None:
            ymin = min(ymin, cur_y)
            ymax = max(ymax, cur_y)
        if cur_z is not None:
            zmin = min(zmin, cur_z)
            zmax = max(zmax, cur_z)

    # If no moves found
    if move_count == 0 or xmin == float('inf'):
        return {
            "ok": False,
            "error": "No motion commands (G0/G1) with XYZ found in the file.",
            "line_count": line_count,
            "move_count": move_count
        }

    dims = {
        "x_min": xmin, "x_max": xmax, "x_size": xmax - xmin,
        "y_min": ymin, "y_max": ymax, "y_size": ymax - ymin,
        "z_min": zmin if zmin != float('inf') else 0.0,
        "z_max": zmax if zmax != float('-inf') else 0.0,
    }
    dims["z_size"] = dims["z_max"] - dims["z_min"]

    return {
        "ok": True,
        "line_count": line_count,
        "move_count": move_count,
        "absolute_mode_assumed": True,
        "result": dims,
    }

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    try:
        report = analyze_gcode(f)
        if not report["ok"]:
            return jsonify(report), 400
        return jsonify(report)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    # Accept raw upload as well
    return analyze()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
