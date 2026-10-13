import os
import re
import uuid
from pathlib import Path

import fitz
import requests
from flask import Flask, jsonify, request, send_from_directory


app = Flask(__name__)

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/output"))
GOTENBERG_URL = os.environ.get(
    "GOTENBERG_URL", "http://host.docker.internal:3000"
).rstrip("/")
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL", "http://localhost:8080"
).rstrip("/")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_filename(title: str) -> str:
    title = (title or "优化学习手册").strip()
    title = re.sub(r"[^\w\-\u4e00-\u9fff ]+", "", title)
    title = re.sub(r"\s+", "-", title)[:80] or "优化学习手册"
    return f"{title}-{uuid.uuid4().hex[:8]}.pdf"


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/inspect")
def inspect_pdf():
    uploaded = request.files.get("file")

    if uploaded is None:
        return jsonify({
            "error": "请以 multipart/form-data 上传名为 file 的 PDF"
        }), 400

    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({
            "error": "上传文件必须是 PDF"
        }), 400

    try:
        pdf_bytes = uploaded.read()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        return jsonify({
            "error": "PDF 无法读取",
            "detail": str(exc)
        }), 400

    pages = []
    text_pages = []
    ocr_pages = []
    skip_pages = []

    for index, page in enumerate(document):
        page_no = index + 1
        text = page.get_text("text") or ""
        text = re.sub(r"\s+", " ", text).strip()
        text_length = len(text)

        images = page.get_images(full=True)
        has_image = len(images) > 0
	        # 矢量图形包括线条、矩形、SVG 转换后的绘图等
        drawings = page.get_drawings()
        has_vector_graphics = len(drawings) > 0

        # 批注和表单也可能包含有效内容
        has_annotations = next(page.annots(), None) is not None
        has_widgets = next(page.widgets(), None) is not None

        has_visuals = has_image or has_vector_graphics

        has_table = False
        try:
            table_result = page.find_tables()
            has_table = len(table_result.tables) > 0
        except Exception:
            has_table = False

        is_blank = (
            text_length == 0
            and not has_visuals
            and not has_annotations
            and not has_widgets
        )
        is_cover = page_no == 1 and not is_blank

        if is_blank:
            source_type = "blank"
            processing = "skip"
            skip_pages.append(page_no)
        elif text_length >= 80 or (text_length > 0 and not has_image):
            source_type = "mixed" if has_image else "text"
            processing = "extract_text"
            text_pages.append(page_no)
        else:
            source_type = "scan"
            processing = "ocr"
            ocr_pages.append(page_no)

        pages.append({
            "page_no": page_no,
            "source_type": source_type,
            "processing": processing,
            "text_length": text_length,
            "has_image": has_image,
            "has_vector_graphics": has_vector_graphics,
            "has_visuals": has_visuals,
            "has_annotations": has_annotations,
            "has_widgets": has_widgets,
            "has_table": has_table,
            "is_blank": is_blank,
            "is_cover": is_cover
        })

    page_count = len(pages)
    non_blank_pages = [
        page for page in pages if not page["is_blank"]
    ]

    if non_blank_pages:
        text_coverage = round(
            len([
                page for page in non_blank_pages
                if page["processing"] == "extract_text"
            ]) / len(non_blank_pages),
            3
        )
    else:
        text_coverage = 0.0

    scan_ratio = round(
        len(ocr_pages) / page_count, 3
    ) if page_count else 0.0

    if text_coverage >= 0.75:
        document_mode = "text"
    elif text_coverage <= 0.25:
        document_mode = "scan"
    else:
        document_mode = "mixed"

    result = {
        "page_count": page_count,
        "document_mode": document_mode,
        "text_coverage": text_coverage,
        "scan_ratio": scan_ratio,
        "pages": pages,
        "text_pages": text_pages,
        "ocr_pages": ocr_pages,
        "skip_pages": skip_pages,
        "has_images": any(page["has_image"] for page in pages),
        "has_vector_graphics": any(
            page["has_vector_graphics"] for page in pages
        ),
        "has_visuals": any(
            page["has_visuals"] for page in pages
        ),
        "has_tables": any(page["has_table"] for page in pages),
        "warnings": []
    }

    if not ocr_pages:
        result["warnings"].append("没有检测到需要 OCR 的页面")

    if skip_pages:
        result["warnings"].append(
            f"检测到 {len(skip_pages)} 个空白页"
        )

    return jsonify(result)

def parse_page_selection(raw_value, page_count):
    """Parse page selection such as 1-4,7,10-12."""
    if raw_value is None:
        return list(range(1, page_count + 1))

    if isinstance(raw_value, str):
        value = raw_value.strip()

        if not value:
            return list(range(1, page_count + 1))

        if value.startswith("[") and value.endswith("]"):
            import json
            try:
                raw_value = json.loads(value)
            except Exception:
                raise ValueError("pages must be a page range such as 1-4,7")
        else:
            value = (
                value
                .replace("，", ",")
                .replace("－", "-")
                .replace("–", "-")
                .replace("—", "-")
            )
            raw_value = value.split(",")

    if isinstance(raw_value, list):
        selected = set()

        for item in raw_value:
            if type(item) is int:
                selected.add(item)
                continue

            token = str(item).strip()
            if re.fullmatch(r"\d+", token):
                selected.add(int(token))
                continue

            match = re.fullmatch(r"(\d+)-(\d+)", token)
            if match:
                start = int(match.group(1))
                end = int(match.group(2))

                if start > end:
                    raise ValueError(f"invalid page range: {token}")

                selected.update(range(start, end + 1))
                continue

            raise ValueError(
                "pages must use formats such as 1, 1-4, or 1-4,7"
            )

        pages = sorted(selected)
    else:
        raise ValueError("pages must be a page range or an integer array")

    invalid = [
        page for page in pages
        if page < 1 or page > page_count
    ]

    if invalid:
        raise ValueError(
            f"page number out of range: {invalid}"
        )

    return pages


@app.post("/extract")
def extract_pdf_text():
    uploaded = request.files.get("file")

    if uploaded is None:
        return jsonify({
            "error": "multipart/form-data must contain a PDF field named file"
        }), 400

    filename = uploaded.filename or ""

    if not filename.lower().endswith(".pdf"):
        return jsonify({
            "error": "uploaded file must be a PDF"
        }), 400

    try:
        pdf_bytes = uploaded.read()

        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            page_count = len(document)

            raw_pages = (
                request.form.get("pages")
                or request.form.get("page_ranges")
            )

            selected_pages = parse_page_selection(
                raw_pages,
                page_count
            )

            pages = []
            text_pages = []
            blank_pages = []

            for page_no in selected_pages:
                page = document[page_no - 1]

                text = page.get_text(
                    "text",
                    sort=True
                ) or ""

                lines = []
                for line in text.splitlines():
                    line = re.sub(r"[ \t]+", " ", line).strip()
                    if line:
                        lines.append(line)

                normalized_text = "\n".join(lines)
                text_length = len(
                    normalized_text.replace("\n", "").strip()
                )

                has_image = bool(page.get_images(full=True))
                has_vector_graphics = bool(page.get_drawings())
                has_annotations = (
                    next(page.annots(), None) is not None
                )
                has_widgets = (
                    next(page.widgets(), None) is not None
                )

                has_table = False
                table_count = 0

                try:
                    table_result = page.find_tables()
                    table_count = len(table_result.tables)
                    has_table = table_count > 0
                except Exception:
                    pass

                has_visuals = (
                    has_image
                    or has_vector_graphics
                )

                is_blank = (
                    text_length == 0
                    and not has_visuals
                    and not has_annotations
                    and not has_widgets
                )

                if is_blank:
                    source_type = "blank"
                    blank_pages.append(page_no)
                elif text_length > 0 and has_image:
                    source_type = "mixed"
                    text_pages.append(page_no)
                elif text_length > 0:
                    source_type = "text"
                    text_pages.append(page_no)
                else:
                    source_type = "scan"

                pages.append({
                    "page_no": page_no,
                    "text": normalized_text,
                    "text_length": text_length,
                    "source_type": source_type,
                    "has_image": has_image,
                    "has_vector_graphics": has_vector_graphics,
                    "has_visuals": has_visuals,
                    "has_annotations": has_annotations,
                    "has_widgets": has_widgets,
                    "has_table": has_table,
                    "table_count": table_count,
                    "is_blank": is_blank
                })

            warnings = []

            if blank_pages:
                warnings.append(
                    f"detected {len(blank_pages)} blank page(s)"
                )

            if not text_pages:
                warnings.append(
                    "no native selectable text was found"
                )

            return jsonify({
                "page_count": page_count,
                "selected_pages": selected_pages,
                "pages": pages,
                "text_pages": text_pages,
                "blank_pages": blank_pages,
                "text_page_count": len(text_pages),
                "warnings": warnings
            })

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    except Exception as exc:
        return jsonify({
            "error": "PDF text extraction failed",
            "detail": str(exc)
        }), 400
@app.post("/render")
def render():
    payload = request.get_json(silent=True) or {}
    html = payload.get("html")

    if not isinstance(html, str) or not html.strip():
        return jsonify({
            "error": "html must be a non-empty string"
        }), 400

    title = payload.get("title", "优化学习手册")

    if "<html" not in html.lower():
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{
    font-family: 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif;
    line-height: 1.8;
    margin: 40px;
    color: #222;
}}
h1, h2, h3 {{
    color: #17324d;
}}
blockquote {{
    background: #f4f7fa;
    padding: 12px 16px;
    border-left: 4px solid #6b9ac4;
}}
</style>
</head>
<body>{html}</body>
</html>"""

    try:
        response = requests.post(
            f"{GOTENBERG_URL}/forms/chromium/convert/html",
            files={
                "files": (
                    "index.html",
                    html.encode("utf-8"),
                    "text/html"
                )
            },
            timeout=180,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({
            "error": "gotenberg request failed",
            "detail": str(exc)
        }), 502

    filename = safe_filename(title)
    (OUTPUT_DIR / filename).write_bytes(response.content)

    return jsonify({
        "pdf_url": f"{PUBLIC_BASE_URL}/files/{filename}",
        "filename": filename
    })


@app.get("/files/<path:filename>")
def files(filename):
    return send_from_directory(
        OUTPUT_DIR,
        filename,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)