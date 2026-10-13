"""Separate renderer, drop-in /render response with additional navigation report.

Keep existing 8080-8083 services unchanged. Run this on host port 8084.
"""
import os
import re
import uuid
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory
from pdf_navigation import add_navigation

app = Flask(__name__)
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', '/data/output'))
GOTENBERG_URL = os.environ.get('GOTENBERG_URL', 'http://host.docker.internal:3000').rstrip('/')
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://localhost:8084').rstrip('/')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.get('/health')
def health():
    return jsonify({'status': 'ok', 'navigation_version': '2026-10-12-v1'})


@app.post('/render')
def render():
    payload = request.get_json(silent=True) or {}
    html = payload.get('html')
    if not isinstance(html, str) or not html.strip() or '<main' not in html.lower():
        return jsonify({'error': '需要含main正文的完整HTML'}), 400
    threshold = payload.get('toc_min_pages', 30)
    if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold < 1:
        return jsonify({'error': 'toc_min_pages必须是正整数'}), 400
    title = payload.get('title', '优化手册')
    title = title if isinstance(title, str) else '优化手册'
    try:
        response = requests.post(
            GOTENBERG_URL + '/forms/chromium/convert/html',
            files={'files': ('index.html', html.encode('utf-8'), 'text/html')},
            data={'generateDocumentOutline': 'true'}, timeout=(10, 180))
        response.raise_for_status()
    except requests.RequestException as error:
        return jsonify({'error': 'gotenberg request failed', 'detail': str(error)}), 502
    try:
        pdf, report = add_navigation(response.content, html, min_pages=threshold, cover_pages=1)
    except Exception as error:
        # Do not claim a required TOC succeeded when heading mapping was incomplete.
        return jsonify({'error': '页码目录处理失败', 'detail': str(error)}), 422
    stem = re.sub(r'[^\w\-\u4e00-\u9fff ]+', '', title.strip())
    stem = re.sub(r'\s+', '-', stem)[:80] or '优化手册'
    filename = stem + '-' + uuid.uuid4().hex[:8] + '.pdf'
    (OUTPUT_DIR / filename).write_bytes(pdf)
    return jsonify({'pdf_url': PUBLIC_BASE_URL + '/files/' + filename,
                    'filename': filename, 'page_count': report['page_count'],
                    'navigation_report': report})


@app.get('/files/<path:filename>')
def files(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
