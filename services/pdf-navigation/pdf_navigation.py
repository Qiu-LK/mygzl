"""Post-process an already rendered PDF. No OCR/LLM; outline supplies real pages."""
import io
import re
import os
from pathlib import Path
from html.parser import HTMLParser

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def toc_font():
    name = 'NavigationChinese'
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    paths = [os.environ.get('TOC_FONT_PATH', ''),
             '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
             'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc']
    for path in paths:
        if path and Path(path).is_file():
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
            return name
    raise ValueError('缺少可嵌入的中文字体，请配置TOC_FONT_PATH')


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.current = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.in_main = True
        if self.in_main and re.fullmatch('h[1-6]', tag):
            self.current = [int(tag[1]), []]

    def handle_data(self, text):
        if self.current:
            self.current[1].append(text)

    def handle_endtag(self, tag):
        if self.current and tag == 'h%d' % self.current[0]:
            title = ''.join(self.current[1]).strip()
            if title:
                self.items.append((self.current[0], title))
            self.current = None
        if tag == 'main':
            self.in_main = False


def normalized(title):
    return re.sub(r'\s+', '', title)


def outline_entries(reader):
    result = []
    def walk(items):
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                page = reader.get_destination_page_number(item)
                if page is not None and page >= 0:
                    result.append({'title': item.title, 'page_index': page,
                                   'top': float(item.top) if item.top is not None else None})
    walk(reader.outline)
    return result


def select_entries(html, reader, cover_pages):
    headings = Headings()
    headings.feed(html)
    # Main h2 is the stable section structure produced by the request node.
    # Only fall back to h1/h3 for other document structures, never list every h3 function.
    levels = [level for level, _ in headings.items]
    selected_level = 2 if 2 in levels else min(levels, default=2)
    candidates = outline_entries(reader)
    selected, cursor = [], 0
    for level, title in headings.items:
        if level != selected_level:
            continue
        match = next((i for i in range(cursor, len(candidates))
                      if candidates[i]['page_index'] >= cover_pages
                      and normalized(candidates[i]['title']) in
                      (normalized(title), normalized(title) * 2, normalized(title) * 3)), None)
        if match is None:
            raise ValueError('目录无法找到标题的真实PDF页码：' + title)
        selected.append(dict(candidates[match], title=title))
        cursor = match + 1
    if not selected:
        raise ValueError('30页以上的PDF没有可定位的正文标题，不能生成虚假目录')
    return selected


def wrap_title(title, font, size, width):
    lines, current = [], ''
    for char in title:
        if current and pdfmetrics.stringWidth(current + char, font, size) > width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines or ['']


def toc_pdf(entries, width, height, offset):
    font = toc_font()
    buffer = io.BytesIO()
    output = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=1)
    margin = min(44, width * .08)
    content_width = width - 2 * margin
    y, page_index = 0, -1
    rows = []

    def new_page():
        nonlocal y, page_index
        if page_index >= 0:
            output.showPage()
        page_index += 1
        output.setFont(font, 21)
        output.drawString(margin, height - 58, '目录' if page_index == 0 else '目录（续）')
        y = height - 120

    new_page()
    for entry in entries:
        lines = wrap_title(entry['title'], font, 11, content_width - 47)
        row_height = 16 * len(lines) + 9
        if y - row_height < 45:
            new_page()
        if row_height > height - 170:
            raise ValueError('目录标题过长，无法安全排版')
        target = entry['page_index'] + offset + 1
        output.setFillColorRGB(.08, .08, .08)
        output.setFont(font, 11)
        for line_index, line in enumerate(lines):
            output.drawString(margin, y - line_index * 16, line)
        # Long titles wrap naturally; the leader and page number follow the last
        # line, never crossing title text or running underneath the page number.
        baseline = y - (len(lines) - 1) * 16
        leader_start = margin + pdfmetrics.stringWidth(lines[-1], font, 11) + 7
        leader_end = width - margin - pdfmetrics.stringWidth(str(target), 'Helvetica', 10) - 7
        if leader_end > leader_start:
            output.saveState()
            output.setStrokeColorRGB(.5, .5, .5)
            output.setLineWidth(.8)
            output.setLineCap(1)
            output.setDash(.1, 3)
            output.line(leader_start, baseline + 2, leader_end, baseline + 2)
            output.restoreState()
        output.setFont('Helvetica', 10)
        output.drawRightString(width - margin, baseline, str(target))
        rows.append({'toc_page': page_index, 'rect': (margin, y - row_height + 6, width - margin, y + 12),
                     'target': entry['page_index'] + offset, 'title': entry['title']})
        y -= row_height
    output.save()
    return buffer.getvalue(), rows


def page_number_overlay(width, height, label):
    buffer = io.BytesIO()
    output = canvas.Canvas(buffer, pagesize=(width, height), pageCompression=1)
    output.setFont('Helvetica', 9)
    output.setFillColorRGB(.25, .25, .25)
    output.drawCentredString(width / 2, 14, str(label))
    output.save()
    return PdfReader(buffer).pages[0]


def add_navigation(pdf_bytes, html, min_pages=30, cover_pages=1):
    if not isinstance(min_pages, int) or isinstance(min_pages, bool) or min_pages < 1:
        raise ValueError('toc_min_pages必须是正整数')
    reader = PdfReader(io.BytesIO(pdf_bytes))
    count = len(reader.pages)
    if cover_pages < 0 or cover_pages >= count:
        raise ValueError('cover_pages无效，或正文没有页面')
    toc_enabled = count >= min_pages
    entries = select_entries(html, reader, cover_pages) if toc_enabled else []
    toc_reader, rows, toc_count = None, [], 0
    first = reader.pages[0]
    width, height = float(first.mediabox.width), float(first.mediabox.height)
    if entries:
        offset = 0
        for _ in range(4):
            toc_bytes, rows = toc_pdf(entries, width, height, offset)
            toc_reader = PdfReader(io.BytesIO(toc_bytes))
            toc_count = len(toc_reader.pages)
            if toc_count == offset:
                break
            offset = toc_count
        else:
            raise ValueError('目录页数未稳定，已停止输出错误页码')
    writer = PdfWriter()
    for page in reader.pages[:cover_pages]:
        writer.add_page(page)
    if toc_reader:
        for page in toc_reader.pages:
            writer.add_page(page)
    for page in reader.pages[cover_pages:]:
        writer.add_page(page)
    from pypdf.annotations import Link
    from pypdf.generic import ArrayObject, NameObject
    for row in rows:
        link = Link(rect=row['rect'], target_page_index=row['target'], border=[0, 0, 0])
        writer.add_annotation(cover_pages + row['toc_page'], link)
        # Use a real page reference (some pypdf versions serialize the zero-based
        # integer instead, which not all viewers accept as a local destination).
        stored = writer.pages[cover_pages + row['toc_page']]['/Annots'][-1].get_object()
        destination = stored['/Dest']
        stored[NameObject('/Dest')] = ArrayObject([writer.pages[row['target']].indirect_reference,
                                                   *destination[1:]])
    # Rebuild bookmarks to point at the shifted real pages, not the old page indexes.
    if toc_reader:
        writer.add_outline_item('目录', cover_pages)
    for entry in entries:
        writer.add_outline_item(entry['title'], entry['page_index'] + toc_count)
    for index, page in enumerate(writer.pages):
        if index >= cover_pages:
            overlay = page_number_overlay(float(page.mediabox.width), float(page.mediabox.height), index + 1)
            page.merge_page(overlay)
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items() if value is not None})
    result = io.BytesIO()
    writer.write(result)
    final_count = len(writer.pages)
    return result.getvalue(), {'base_page_count': count, 'page_count': final_count,
                              'toc_enabled': toc_enabled, 'toc_pages': toc_count,
                              'toc_entries': len(entries), 'toc_threshold': min_pages,
                              'threshold_basis': 'rendered_pdf_before_toc_including_cover',
                              'numbering': 'physical_pdf_page_index_cover_hidden',
                              'page_numbers_added': True,
                              'entries': [{'title': e['title'], 'page': e['page_index'] + toc_count + 1}
                                          for e in entries]}
