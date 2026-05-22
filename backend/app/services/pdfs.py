from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from typing import Any

from fpdf import FPDF


def _pdf_output_bytes(pdf: FPDF) -> bytes:
    data = pdf.output(dest="S")
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    return str(data).encode("latin-1")


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _pdf_safe(text: str) -> str:
    """FPDF core fonts are Latin-1; replace unsupported characters."""
    if not text:
        return " "
    return _strip_html(str(text)).encode("latin-1", "replace").decode("latin-1")


def _break_long_tokens(text: str, max_chunk: int = 60) -> str:
    """Insert break points so FPDF can wrap very long words/URLs."""
    out: list[str] = []
    for token in re.split(r"(\s+)", text):
        if not token or token.isspace():
            out.append(token)
            continue
        while len(token) > max_chunk:
            out.append(token[:max_chunk])
            out.append(" ")
            token = token[max_chunk:]
        out.append(token)
    return "".join(out).strip() or " "


class _QuizReviewPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self.set_margins(14, 14, 14)

    @property
    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}/{{nb}}", align="C")

    def write_block(self, text: str, *, h: float = 5, style: str = "", size: int = 10) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", style, size)
        body = _pdf_safe(_break_long_tokens(text))
        self.multi_cell(self.content_width, h, body or " ")

    def write_line(self, text: str, *, h: float = 7, style: str = "", size: int = 11) -> None:
        self.set_x(self.l_margin)
        self.set_font("Helvetica", style, size)
        self.cell(self.content_width, h, _pdf_safe(text), ln=1)


def build_quiz_review_pdf(
    *,
    user_email: str,
    exam_title: str,
    attempt_no: int,
    total_questions: int,
    total_answered: int,
    total_correct: int,
    total_wrong: int,
    total_marks: float,
    reviews: list[dict[str, Any]],
    user_name: str | None = None,
) -> bytes:
    pdf = _QuizReviewPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    pdf.set_text_color(26, 35, 50)
    pdf.write_line("Critical Care Classes - Exam Review", size=16, style="B")

    pdf.set_text_color(80, 80, 80)
    pdf.write_line(
        f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC",
        size=10,
        style="",
    )
    pdf.ln(2)

    pdf.set_text_color(26, 35, 50)
    pdf.write_line(_pdf_safe(exam_title) or "Mock Test", size=13, style="B")

    pdf.set_text_color(40, 40, 40)
    if user_name:
        pdf.write_line(f"Candidate: {user_name}", size=11)
    pdf.write_line(f"Email: {user_email}", size=11)
    pdf.write_line(f"Attempt: {attempt_no}", size=11)
    pdf.ln(3)

    pdf.set_fill_color(244, 246, 250)
    pdf.write_line("Score summary", style="B", size=11)
    pdf.ln(1)

    for label, value in [
        ("Total questions:", str(total_questions)),
        ("Attempted:", str(total_answered)),
        ("Correct:", str(total_correct)),
        ("Incorrect:", str(total_wrong)),
        ("Final score:", f"{total_marks:.2f}"),
    ]:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(48, 6, _pdf_safe(label), border=0)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(pdf.content_width - 48, 6, _pdf_safe(value), ln=1)

    pdf.ln(4)
    pdf.write_line("Detailed question review", style="B", size=12)
    pdf.ln(2)

    for idx, rev in enumerate(reviews, start=1):
        is_correct = bool(rev.get("is_correct"))
        status = "CORRECT" if is_correct else "INCORRECT"
        user_ans = rev.get("user_answer") or []
        correct_ans = rev.get("correct_answer") or []
        marks = float(rev.get("marks") or 0)
        neg = float(rev.get("negative_mark") or 0)

        if pdf.get_y() > 265:
            pdf.add_page()

        if is_correct:
            pdf.set_text_color(4, 168, 126)
        else:
            pdf.set_text_color(220, 38, 38)
        pdf.write_line(f"Question {idx} - {status}", style="B", size=11)

        pdf.set_text_color(26, 35, 50)
        q_text = str(rev.get("text") or "")
        pdf.write_block(q_text or "(No question text)", size=10)
        pdf.ln(1)

        pdf.set_text_color(60, 60, 60)
        meta = (
            f"Your answer: {', '.join(str(x) for x in user_ans) if user_ans else 'Not attempted'} | "
            f"Correct: {', '.join(str(x) for x in correct_ans) if correct_ans else '-'} | "
            f"Marks: {marks:.2f} | Negative: {neg:.2f}"
        )
        pdf.write_block(meta, size=9)
        pdf.ln(1)

        for opt in rev.get("options") or []:
            key = str(opt.get("key") or "").upper()
            opt_text = str(opt.get("text") or "").strip() or "(empty option)"
            tags: list[str] = []
            if key in [str(x).upper() for x in user_ans]:
                tags.append("YOUR CHOICE")
            if key in [str(x).upper() for x in correct_ans]:
                tags.append("CORRECT")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            line = f"{key}. {opt_text}{tag_str}"
            pdf.write_block(line, size=9, style="B" if tags else "")

        pdf.ln(3)

    return _pdf_output_bytes(pdf)


def quiz_result_pdf(
    *,
    user_email: str,
    exam_title: str,
    total_questions: int,
    total_answered: int,
    total_correct: int,
    total_wrong: int,
    total_marks: float,
    user_name: str | None = None,
    attempt_no: int = 1,
    reviews: list[dict[str, Any]] | None = None,
) -> bytes:
    """Backward-compatible entry: detailed PDF when reviews provided, else summary-only."""
    if reviews:
        return build_quiz_review_pdf(
            user_email=user_email,
            user_name=user_name,
            exam_title=exam_title,
            attempt_no=attempt_no,
            total_questions=total_questions,
            total_answered=total_answered,
            total_correct=total_correct,
            total_wrong=total_wrong,
            total_marks=total_marks,
            reviews=reviews,
        )

    pdf = FPDF()
    pdf.set_margins(14, 14, 14)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=14)
    w = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(w, 10, _pdf_safe("Critical Care Classes - Quiz Result"), ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(w, 8, _pdf_safe(f"Generated: {datetime.utcnow().isoformat()} UTC"), ln=1)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(w, 8, _pdf_safe(exam_title), ln=1)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(w, 7, _pdf_safe(f"User: {user_email}"), ln=1)
    pdf.ln(2)

    def row(label: str, value: str) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(55, 7, _pdf_safe(label), ln=0)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(w - 55, 7, _pdf_safe(value), ln=1)

    row("Total questions:", str(total_questions))
    row("Attempted:", str(total_answered))
    row("Correct:", str(total_correct))
    row("Wrong:", str(total_wrong))
    row("Final score:", f"{total_marks:.1f}")
    return _pdf_output_bytes(pdf)
