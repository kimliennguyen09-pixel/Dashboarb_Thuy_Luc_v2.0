from __future__ import annotations

import csv
import io
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "Bang thong ke.csv"
NUMERIC_COLUMNS = {
    "Elevation (Ground) (m)", "Elevation (Rim) (m)", "Elevation (Invert) (m)",
    "Flow (Total In) (L/s)", "Flow (Total Out) (L/s)", "Depth (Out) (m)",
    "Depth (Flooding) (m)", "Depth (Surcharged) (m)",
    "Hydraulic Grade Line (Out) (m)", "Hydraulic Grade Line (In) (m)",
}
RISK_VALUES = {"all", "Critical", "Warning", "Normal"}
CHART_VALUES = {"top_flow", "lowest_hgl_margin", "flood_depth", "risk_profile"}
FILTER_KEYS = {"risk", "q", "min_flood_depth", "max_flood_depth", "limit"}
REQUIRED_UPLOAD_COLUMNS = {"ID", "Label", "Is Overflowing?", *NUMERIC_COLUMNS}
MAX_UPLOAD_ROWS = 10_000


class QueryValidationError(ValueError):
    """Lỗi dữ liệu đầu vào do người dùng gửi qua query string."""


def load_nodes(data_file: Path = DATA_FILE) -> list[dict[str, Any]]:
    if not data_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu: {data_file}")
    with data_file.open(encoding="utf-8-sig", newline="") as handle:
        nodes = list(csv.DictReader(handle))
    for row in nodes:
        for key in NUMERIC_COLUMNS:
            try:
                row[key] = float(row.get(key, 0))
            except (TypeError, ValueError):
                row[key] = 0.0
        row["Is Overflowing?"] = str(row.get("Is Overflowing?", "")).strip().lower() in {"true", "1", "yes"}
        rim = row["Elevation (Rim) (m)"]
        invert = row["Elevation (Invert) (m)"]
        hgl = max(row["Hydraulic Grade Line (In) (m)"], row["Hydraulic Grade Line (Out) (m)"])
        row["Available Depth (m)"] = round(rim - invert, 3)
        row["HGL Margin (m)"] = round(rim - hgl, 3)
        row["Fill Ratio (%)"] = round(100 * row["Depth (Out) (m)"] / max(row["Available Depth (m)"], 0.001), 1)

        flooding = row["Depth (Flooding) (m)"]
        if flooding <= 0:
            row["Flood Level"] = "None"
        elif flooding <= 0.10:
            row["Flood Level"] = "Low"
        elif flooding <= 0.30:
            row["Flood Level"] = "Moderate"
        elif flooding <= 0.50:
            row["Flood Level"] = "High"
        else:
            row["Flood Level"] = "Very High"

        reasons = []
        if flooding > 0:
            reasons.append(f"Ngập sâu {flooding:.2f} m")
        if row["Is Overflowing?"]:
            reasons.append("Nút đang tràn")
        if row["HGL Margin (m)"] <= 0:
            reasons.append("HGL bằng/vượt cao độ nắp")
        elif row["HGL Margin (m)"] < 0.5:
            reasons.append("Biên an toàn HGL dưới 0,50 m")
        if row["Fill Ratio (%)"] >= 100:
            reasons.append("Nút đầy hoặc quá tải")
        elif row["Fill Ratio (%)"] >= 75:
            reasons.append("Tỷ lệ đầy từ 75%")
        row["Warning Reasons"] = reasons
        if row["Is Overflowing?"] or flooding > 0 or row["HGL Margin (m)"] <= 0:
            row["Risk"] = "Critical"
        elif row["HGL Margin (m)"] < 0.5 or row["Fill Ratio (%)"] >= 75:
            row["Risk"] = "Warning"
        else:
            row["Risk"] = "Normal"
    return nodes


NODES = load_nodes()


def parse_float(name: str, value: str | None, minimum: float | None = None) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise QueryValidationError(f"'{name}' phải là một số hợp lệ.") from exc
    if not math.isfinite(parsed):
        raise QueryValidationError(f"'{name}' phải là một số hữu hạn.")
    if minimum is not None and parsed < minimum:
        raise QueryValidationError(f"'{name}' phải lớn hơn hoặc bằng {minimum}.")
    return parsed


def parse_int(name: str, value: str | None, default: int, minimum: int, maximum: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise QueryValidationError(f"'{name}' phải là số nguyên.") from exc
    if not minimum <= parsed <= maximum:
        raise QueryValidationError(f"'{name}' phải nằm trong khoảng {minimum}–{maximum}.")
    return parsed


def validate_filters(args, extra_allowed: set[str] | None = None) -> dict[str, Any]:
    allowed = FILTER_KEYS | (extra_allowed or set())
    unknown = sorted(set(args.keys()) - allowed)
    if unknown:
        raise QueryValidationError(f"Tham số không được hỗ trợ: {', '.join(unknown)}.")
    repeated = sorted(key for key in args.keys() if len(args.getlist(key)) > 1)
    if repeated:
        raise QueryValidationError(f"Không được lặp lại tham số: {', '.join(repeated)}.")
    risk = args.get("risk", "all").strip()
    if risk not in RISK_VALUES:
        raise QueryValidationError("'risk' chỉ nhận all, Critical, Warning hoặc Normal.")
    search = args.get("q", "").strip()
    if len(search) > 100:
        raise QueryValidationError("'q' không được dài quá 100 ký tự.")
    min_flood = parse_float("min_flood_depth", args.get("min_flood_depth"), 0)
    max_flood = parse_float("max_flood_depth", args.get("max_flood_depth"), 0)
    if min_flood is not None and max_flood is not None and min_flood > max_flood:
        raise QueryValidationError("'min_flood_depth' không được lớn hơn 'max_flood_depth'.")
    return {
        "risk": risk,
        "q": search,
        "min_flood_depth": min_flood,
        "max_flood_depth": max_flood,
        "limit": parse_int("limit", args.get("limit"), 12, 1, 50),
    }


def validate_uploaded_csv(path: Path) -> int:
    """Kiểm tra cấu trúc và giá trị CSV trước khi thay dữ liệu đang sử dụng."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            missing = sorted(REQUIRED_UPLOAD_COLUMNS - headers)
            if missing:
                raise QueryValidationError(f"CSV thiếu cột bắt buộc: {', '.join(missing)}.")
            seen_ids: set[str] = set()
            count = 0
            for line_number, row in enumerate(reader, start=2):
                count += 1
                if count > MAX_UPLOAD_ROWS:
                    raise QueryValidationError(f"CSV vượt quá {MAX_UPLOAD_ROWS:,} dòng dữ liệu.")
                node_id = str(row.get("ID", "")).strip()
                if not node_id:
                    raise QueryValidationError(f"Dòng {line_number}: ID không được để trống.")
                if node_id in seen_ids:
                    raise QueryValidationError(f"Dòng {line_number}: ID '{node_id}' bị trùng.")
                seen_ids.add(node_id)
                for column in NUMERIC_COLUMNS:
                    raw = str(row.get(column, "")).strip()
                    try:
                        value = float(raw)
                    except ValueError as exc:
                        raise QueryValidationError(
                            f"Dòng {line_number}, cột '{column}': phải là số hợp lệ."
                        ) from exc
                    if not math.isfinite(value):
                        raise QueryValidationError(
                            f"Dòng {line_number}, cột '{column}': phải là số hữu hạn."
                        )
                overflow = str(row.get("Is Overflowing?", "")).strip().lower()
                if overflow not in {"true", "false", "1", "0", "yes", "no"}:
                    raise QueryValidationError(
                        f"Dòng {line_number}, cột 'Is Overflowing?': chỉ nhận true/false."
                    )
    except UnicodeDecodeError as exc:
        raise QueryValidationError("CSV phải sử dụng mã hóa UTF-8 hoặc UTF-8 BOM.") from exc
    if count == 0:
        raise QueryValidationError("CSV không có dòng dữ liệu.")
    return count


def filter_nodes(nodes: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    search = filters["q"].casefold()
    rows = []
    for node in nodes:
        depth = node["Depth (Flooding) (m)"]
        if filters["risk"] != "all" and node["Risk"] != filters["risk"]:
            continue
        if search and search not in str(node.get("Label", "")).casefold() and search not in str(node.get("ID", "")).casefold():
            continue
        if filters["min_flood_depth"] is not None and depth < filters["min_flood_depth"]:
            continue
        if filters["max_flood_depth"] is not None and depth > filters["max_flood_depth"]:
            continue
        rows.append(node)
    return rows


def make_summary(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(nodes)
    flows = [n["Flow (Total Out) (L/s)"] for n in nodes]
    margins = [n["HGL Margin (m)"] for n in nodes]
    risks = {key: sum(n["Risk"] == key for n in nodes) for key in ("Critical", "Warning", "Normal")}
    levels = {key: sum(n["Flood Level"] == key for n in nodes) for key in ("Very High", "High", "Moderate", "Low", "None")}
    flooded = [n for n in nodes if n["Depth (Flooding) (m)"] > 0]
    return {
        "total_nodes": total,
        "overflowing": sum(n["Is Overflowing?"] for n in nodes),
        "max_flow": round(max(flows, default=0), 2),
        "avg_flow": round(sum(flows) / total, 2) if total else 0,
        "max_depth_out": round(max((n["Depth (Out) (m)"] for n in nodes), default=0), 2),
        "min_hgl_margin": round(min(margins, default=0), 2),
        "flooded_nodes": len(flooded),
        "max_flood_depth": round(max((n["Depth (Flooding) (m)"] for n in flooded), default=0), 2),
        "avg_flood_depth": round(sum(n["Depth (Flooding) (m)"] for n in flooded) / len(flooded), 2) if flooded else 0,
        "flood_levels": levels,
        "risks": risks,
    }


def summary() -> dict[str, Any]:
    """Giữ tương thích với code và bộ kiểm thử của phiên bản cũ."""
    return make_summary(NODES)


def build_chart_data(nodes: list[dict[str, Any]], limit: int) -> dict[str, list[dict[str, Any]]]:
    return {
        "top_flow": sorted(nodes, key=lambda n: n["Flow (Total Out) (L/s)"], reverse=True)[:limit],
        "lowest_hgl_margin": sorted(nodes, key=lambda n: n["HGL Margin (m)"])[:limit],
        "flood_depth": sorted((n for n in nodes if n["Depth (Flooding) (m)"] > 0), key=lambda n: n["Depth (Flooding) (m)"], reverse=True)[:limit],
    }


def csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    output = io.StringIO(newline="")
    fieldnames = list(rows[0].keys()) if rows else ["ID", "Label", "Message"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for node in rows:
        row = dict(node)
        row["Warning Reasons"] = "; ".join(row.get("Warning Reasons", []))
        writer.writerow(row)
    response = Response(output.getvalue().encode("utf-8-sig"), mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    return response


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
    origins = "*" if origins_raw == "*" else [item.strip() for item in origins_raw.split(",") if item.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins}}, methods=["GET", "POST", "OPTIONS"])

    @app.after_request
    def no_cache_api(response):
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(QueryValidationError)
    def handle_validation_error(error):
        return jsonify({"error": "invalid_query", "message": str(error)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"error": error.name.lower().replace(" ", "_"), "message": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled dashboard error", exc_info=error)
        return jsonify({"error": "internal_server_error", "message": "Máy chủ gặp lỗi khi xử lý yêu cầu."}), 500

    @app.get("/")
    def dashboard_page():
        return render_template("index.html")

    @app.get("/node")
    def node_page():
        return render_template("node-detail.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "records": len(NODES)})

    @app.get("/api/summary")
    def summary_api():
        filters = validate_filters(request.args)
        rows = filter_nodes(NODES, filters)
        return jsonify({**make_summary(rows), "filters": filters})

    @app.get("/api/nodes")
    def nodes_api():
        filters = validate_filters(request.args)
        rows = filter_nodes(NODES, filters)
        return jsonify({
            "count": len(rows),
            "items": rows,
            "filters": filters,
            "empty": not rows,
            "message": "Không có dữ liệu phù hợp với bộ lọc." if not rows else "",
        })

    @app.get("/api/nodes/<node_id>")
    def node_api(node_id: str):
        if len(node_id) > 64:
            raise QueryValidationError("ID nút không được dài quá 64 ký tự.")
        node = next((item for item in NODES if str(item["ID"]) == node_id), None)
        if node is None:
            return jsonify({"error": "node_not_found", "message": f"Không tìm thấy nút '{node_id}'."}), 404
        return jsonify(node)

    @app.get("/api/charts")
    def charts_api():
        filters = validate_filters(request.args)
        rows = filter_nodes(NODES, filters)
        charts = build_chart_data(rows, filters["limit"])
        return jsonify({
            **charts,
            "count": len(rows),
            "empty": not rows,
            "message": "Không có dữ liệu biểu đồ phù hợp với bộ lọc." if not rows else "",
            "filters": filters,
        })

    @app.get("/api/charts/export.csv")
    def export_chart_csv():
        filters = validate_filters(request.args, {"chart"})
        chart = request.args.get("chart", "top_flow").strip()
        if chart not in CHART_VALUES:
            raise QueryValidationError("'chart' chỉ nhận top_flow, lowest_hgl_margin, flood_depth hoặc risk_profile.")
        rows = filter_nodes(NODES, filters)
        selected = rows if chart == "risk_profile" else build_chart_data(rows, filters["limit"])[chart]
        return csv_response(selected, f"GeoAI_{chart}.csv")

    @app.post("/api/data/upload")
    def upload_data_csv():
        """Nhận CSV, kiểm tra toàn bộ dữ liệu rồi mới thay dataset hiện tại."""
        global NODES
        if "file" not in request.files:
            raise QueryValidationError("Thiếu trường file trong biểu mẫu upload.")
        uploaded = request.files["file"]
        filename = (uploaded.filename or "").strip()
        if not filename:
            raise QueryValidationError("Chưa chọn file CSV.")
        if Path(filename).suffix.lower() != ".csv":
            raise QueryValidationError("Chỉ chấp nhận file có phần mở rộng .csv.")

        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="hydraulic_upload_", suffix=".csv", dir=DATA_FILE.parent, delete=False
            ) as temp_file:
                temp_path = Path(temp_file.name)
                uploaded.save(temp_file)
            count = validate_uploaded_csv(temp_path)
            new_nodes = load_nodes(temp_path)
            if DATA_FILE.exists():
                shutil.copy2(DATA_FILE, DATA_FILE.with_suffix(".backup.csv"))
            os.replace(temp_path, DATA_FILE)
            temp_path = None
            NODES = new_nodes
            return jsonify({
                "status": "ok",
                "records": count,
                "message": f"Đã tải và kích hoạt {count} nút thủy lực.",
            })
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("DASHBOARD_PORT", "8000")))
    app.run(host=os.getenv("DASHBOARD_HOST", "0.0.0.0"), port=port, debug=False)
