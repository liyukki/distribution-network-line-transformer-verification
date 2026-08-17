"""Build the Chinese project paper PDF from its controlled Markdown source."""

from __future__ import annotations

import argparse
import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "paper" / "line-transformer-verification-paper.md"
DEFAULT_OUTPUT = ROOT / "paper" / "line-transformer-verification-paper.pdf"
FONT_REGULAR = "PaperChinese"
FONT_BOLD = "PaperChineseBold"


def _register_fonts() -> None:
    candidates = (
        (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/msyhbd.ttc"),
        ),
        (
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simhei.ttf"),
        ),
    )
    last_error: Exception | None = None
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
                pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
                return
            except Exception as exc:  # noqa: BLE001 - record and try known fallback
                last_error = exc
    raise RuntimeError(
        "未找到可用于论文 PDF 的中文字体。Windows 需要微软雅黑或黑体；"
        "其他系统请在 _register_fonts() 中配置可嵌入的中文 TTF 字体。"
    ) from last_error


def _citation_order(bibliography: Path) -> dict[str, int]:
    text = bibliography.read_text(encoding="utf-8")
    keys = re.findall(r"@\w+\{([^,]+),", text)
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("references.bib 为空或包含重复 citation key")
    return {key: index + 1 for index, key in enumerate(keys)}


def _inline_markup(text: str, citations: dict[str, int]) -> str:
    """Convert the intentionally small inline Markdown subset to ReportLab XML."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n")
    protected: dict[str, str] = {}

    def protect(value: str) -> str:
        key = f"@@INLINE{len(protected)}@@"
        protected[key] = value
        return key

    text = re.sub(
        r"\[([^]]+)\]\((https?://[^)]+)\)",
        lambda match: protect(
            f'<link href="{escape(match.group(2))}" color="#1D4ED8">{escape(match.group(1))}</link>'
        ),
        text,
    )
    text = re.sub(
        r"\$([^$]+)\$",
        lambda match: protect(
            f'<font name="{FONT_REGULAR}" color="#334155">'
            f"{escape(_math_to_text(match.group(1)))}</font>"
        ),
        text,
    )
    text = re.sub(
        r"\[@([A-Za-z0-9_:-]+)\]",
        lambda match: f"[{citations[match.group(1)]}]",
        text,
    )
    text = escape(text)
    text = re.sub(r"`([^`]+)`", rf'<font name="{FONT_REGULAR}" color="#7C2D12">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = text.replace("\n", "<br/>")
    for key, value in protected.items():
        text = text.replace(escape(key), value)
    return text


def _math_to_text(formula: str) -> str:
    """Convert short inline LaTeX expressions to readable Unicode/plain text."""
    replacements = {
        r"\mathbb{I}": "𝕀",
        r"\neq": "≠",
        r"\ldots": "…",
        r"\times": "×",
        r"\Delta": "Δ",
        r"\sigma": "σ",
        r"\mu": "μ",
        r"\rho": "ρ",
        r"\in": "∈",
        r"\le": "≤",
        r"\ge": "≥",
        r"\hat ": "hat ",
        r"\bar": "bar",
        r"\left": "",
        r"\right": "",
        r"\,": " ",
    }
    text = formula
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\\mathcal\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\\hat\s*([A-Za-z])", r"\1-hat", text)
    text = re.sub(r"\\bar\{([^{}]+)\}", r"\1-bar", text)
    text = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", text)
    text = re.sub(r"_\{([^{}]+)\}", r"_(\1)", text)
    return text.replace(r"\{", "{").replace(r"\}", "}")


def _equation_flowable(formula: str, max_width: float) -> Image:
    """Render a display equation with Matplotlib mathtext for the PDF."""
    figure = Figure(figsize=(8.0, 0.65), dpi=180)
    FigureCanvasAgg(figure)
    figure.text(0.5, 0.5, f"${formula}$", ha="center", va="center", fontsize=13)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.08)
    buffer.seek(0)
    image = Image(buffer)
    ratio = min(max_width / image.imageWidth, 18 * mm / image.imageHeight, 1.0)
    image.drawWidth = image.imageWidth * ratio
    image.drawHeight = image.imageHeight * ratio
    image.hAlign = "CENTER"
    return image


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PaperTitle",
            parent=sample["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "PaperSubtitle",
            parent=sample["Normal"],
            fontName=FONT_REGULAR,
            fontSize=11,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "PaperH1",
            parent=sample["Heading1"],
            fontName=FONT_BOLD,
            fontSize=17,
            leading=24,
            textColor=colors.HexColor("#0F4C5C"),
            spaceBefore=14,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "PaperH2",
            parent=sample["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=19,
            textColor=colors.HexColor("#1E3A5F"),
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "PaperBody",
            parent=sample["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=18,
            alignment=TA_JUSTIFY,
            firstLineIndent=21,
            textColor=colors.HexColor("#111827"),
            spaceAfter=7,
            splitLongWords=True,
            wordWrap="CJK",
        ),
        "list": ParagraphStyle(
            "PaperList",
            parent=sample["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.2,
            leading=17,
            leftIndent=18,
            firstLineIndent=-11,
            spaceAfter=4,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "PaperCaption",
            parent=sample["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceBefore=4,
            spaceAfter=10,
        ),
        "equation": ParagraphStyle(
            "PaperEquation",
            parent=sample["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=15,
            alignment=TA_CENTER,
            leftIndent=12,
            rightIndent=12,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.6,
            borderPadding=7,
            backColor=colors.HexColor("#F8FAFC"),
            spaceBefore=5,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "PaperCode",
            parent=sample["Code"],
            fontName=FONT_REGULAR,
            fontSize=7.8,
            leading=12,
            alignment=TA_LEFT,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.6,
            borderPadding=7,
            backColor=colors.HexColor("#F1F5F9"),
            spaceBefore=4,
            spaceAfter=8,
            wordWrap="CJK",
        ),
        "toc_title": ParagraphStyle(
            "TOCTitle",
            parent=sample["Heading1"],
            fontName=FONT_BOLD,
            fontSize=18,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0F4C5C"),
            spaceAfter=18,
        ),
        "table": ParagraphStyle(
            "PaperTable",
            parent=sample["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.4,
            leading=12,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
    }


class PaperDocTemplate(BaseDocTemplate):
    """A4 paper template with bookmarks and a generated table of contents."""

    def __init__(self, filename: str, *, title: str) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=22 * mm,
            rightMargin=22 * mm,
            topMargin=22 * mm,
            bottomMargin=20 * mm,
            title=title,
            author="电气工程本科项目",
            subject="配电网线变关系智能校验研究型软件原型",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="paper-frame",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="paper", frames=[frame], onPage=self._draw_page))
        self._heading_index = 0

    def beforeDocument(self) -> None:
        self._heading_index = 0

    def _draw_page(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT_REGULAR, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        if doc.page > 1:
            canvas.drawString(self.leftMargin, A4[1] - 13 * mm, "配电网线变关系智能校验项目论文")
            canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
            canvas.line(self.leftMargin, A4[1] - 15 * mm, A4[0] - self.rightMargin, A4[1] - 15 * mm)
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"第 {doc.page} 页")
        canvas.restoreState()

    def afterFlowable(self, flowable) -> None:
        level = getattr(flowable, "toc_level", None)
        if level is None:
            return
        self._heading_index += 1
        key = f"heading-{self._heading_index}"
        text = flowable.getPlainText()
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, key))


def _heading(text: str, level: int, styles: dict[str, ParagraphStyle]) -> Paragraph:
    style = styles["h1" if level == 0 else "h2"]
    paragraph = Paragraph(escape(text), style)
    paragraph.toc_level = level
    return paragraph


def _image_flowables(
    source: Path,
    target: str,
    caption: str,
    max_width: float,
    styles: dict[str, ParagraphStyle],
) -> list:
    image_path = (source.parent / target).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"论文图片不存在: {target}")
    image = Image(str(image_path))
    ratio = min(max_width / image.imageWidth, 125 * mm / image.imageHeight, 1.0)
    image.drawWidth = image.imageWidth * ratio
    image.drawHeight = image.imageHeight * ratio
    image.hAlign = "CENTER"
    return [Spacer(1, 4), image, Paragraph(escape(caption), styles["caption"])]


def _table_flowable(
    lines: list[str], max_width: float, citations: dict[str, int], styles: dict[str, ParagraphStyle]
) -> Table:
    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    if not rows or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("论文 Markdown 表格列数不一致")
    data = [
        [Paragraph(_inline_markup(cell, citations), styles["table"]) for cell in row]
        for row in rows
    ]
    column_count = len(data[0])
    table = Table(data, colWidths=[max_width / column_count] * column_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEFEF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _parse_markdown(
    source: Path,
    lines: list[str],
    citations: dict[str, int],
    styles: dict[str, ParagraphStyle],
    max_width: float,
) -> list:
    story: list = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines)
            story.append(Paragraph(_inline_markup(text, citations), styles["body"]))
            paragraph_lines.clear()

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            flush_paragraph()
            index += 1
            continue
        heading_match = re.match(r"^(#{2,3})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            level = 0 if len(heading_match.group(1)) == 2 else 1
            story.append(_heading(heading_match.group(2), level, styles))
            index += 1
            continue
        image_match = re.match(r"^!\[([^]]+)\]\(([^)]+)\)$", line)
        if image_match:
            flush_paragraph()
            story.extend(
                _image_flowables(
                    source,
                    image_match.group(2),
                    image_match.group(1),
                    max_width,
                    styles,
                )
            )
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index].rstrip())
                index += 1
            story.append(_table_flowable(table_lines, max_width, citations, styles))
            story.append(Spacer(1, 8))
            continue
        if line.startswith("```"):
            flush_paragraph()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index].rstrip())
                index += 1
            if index >= len(lines):
                raise ValueError("论文 Markdown 存在未闭合代码块")
            code = "<br/>".join(escape(value or " ") for value in code_lines)
            story.append(Paragraph(code, styles["code"]))
            index += 1
            continue
        if line == "$$":
            flush_paragraph()
            formula_lines: list[str] = []
            index += 1
            while index < len(lines) and lines[index].strip() != "$$":
                formula_lines.append(lines[index].strip())
                index += 1
            if index >= len(lines):
                raise ValueError("论文 Markdown 存在未闭合公式块")
            formula = " ".join(formula_lines)
            story.extend(
                [
                    Spacer(1, 4),
                    _equation_flowable(formula, max_width),
                    Spacer(1, 7),
                ]
            )
            index += 1
            continue
        if re.match(r"^[-*]\s+", line):
            flush_paragraph()
            value = re.sub(r"^[-*]\s+", "", line)
            story.append(Paragraph("•　" + _inline_markup(value, citations), styles["list"]))
            index += 1
            continue
        if re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            story.append(Paragraph(_inline_markup(line, citations), styles["list"]))
            index += 1
            continue
        paragraph_lines.append(line)
        index += 1
    flush_paragraph()
    return story


def build_pdf(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT) -> Path:
    """Build and return the A4 paper PDF path."""
    source = Path(source).resolve()
    output = Path(output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    bibliography = source.parent / "references.bib"
    if not bibliography.is_file():
        raise FileNotFoundError(bibliography)
    _register_fonts()
    styles = _styles()
    citations = _citation_order(bibliography)
    lines = source.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("论文第一行必须是一级标题")
    title = lines[0][2:].strip()
    abstract_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## 摘要"), None
    )
    if abstract_index is None:
        raise ValueError("论文缺少摘要标题")

    output.parent.mkdir(parents=True, exist_ok=True)
    document = PaperDocTemplate(str(output), title=title)
    story: list = [Spacer(1, 45 * mm), Paragraph(escape(title), styles["title"])]
    metadata = [
        re.sub(r"\*\*|<br>", "", line).strip() for line in lines[1:abstract_index] if line.strip()
    ]
    for value in metadata:
        story.append(Paragraph(escape(value), styles["subtitle"]))
    story.extend(
        [
            Spacer(1, 22 * mm),
            Paragraph(
                "合成数据 · 可解释算法 · 公开证据 · 诚实失效边界",
                ParagraphStyle(
                    "CoverTag",
                    parent=styles["subtitle"],
                    fontName=FONT_BOLD,
                    fontSize=12,
                    textColor=colors.HexColor("#0F766E"),
                    borderColor=colors.HexColor("#5EEAD4"),
                    borderWidth=0.8,
                    borderPadding=8,
                ),
            ),
            Spacer(1, 38 * mm),
            Paragraph(
                "本论文全部实验结果来自仓库公开合成证据，不包含真实电网数据。",
                styles["subtitle"],
            ),
            PageBreak(),
            Paragraph("目录", styles["toc_title"]),
        ]
    )
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOCLevel1",
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=18,
            leftIndent=0,
            firstLineIndent=0,
            textColor=colors.HexColor("#0F172A"),
        ),
        ParagraphStyle(
            "TOCLevel2",
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=16,
            leftIndent=18,
            firstLineIndent=0,
            textColor=colors.HexColor("#334155"),
        ),
    ]
    story.extend([toc, PageBreak()])
    story.extend(
        _parse_markdown(
            source,
            lines[abstract_index:],
            citations,
            styles,
            document.width,
        )
    )
    document.multiBuild(story)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="构建线变关系智能校验项目论文 PDF")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_pdf(args.source, args.output)
    print(result.relative_to(ROOT) if result.is_relative_to(ROOT) else result)


if __name__ == "__main__":
    main()
