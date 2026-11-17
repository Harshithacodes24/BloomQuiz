"""
exporter.py
===========
Export module for AI Assessment Studio.
Provides functions to generate:
  - Formatted UTF-8 CSV exports using pandas (questions_to_csv)
  - Clean, professional, printable PDF assessments using fpdf2 (questions_to_pdf)
    with a dedicated Answer Key & Explanations page and Latin-1 Unicode sanitization.
"""

import io
from typing import List, Optional
import pandas as pd
from fpdf import FPDF
from generator import QuestionItem, EvaluationReport


# ==============================================================================
# Unicode Sanitization Helper for FPDF (Latin-1 Safe)
# ==============================================================================

def sanitize_for_pdf(text: str) -> str:
    """
    Sanitizes Unicode text to Latin-1 compatible characters to prevent
    UnicodeEncodeError in FPDF standard fonts (Helvetica, Times, Courier).
    Converts curly quotes, em/en dashes, bullets, math symbols, and ellipsis.
    """
    if not text:
        return ""

    replacements = {
        "\u2018": "'",   # Left single quote
        "\u2019": "'",   # Right single quote / apostrophe
        "\u201a": "'",   # Single low-9 quote
        "\u201b": "'",   # Single high-reversed-9 quote
        "\u201c": '"',   # Left double quote
        "\u201d": '"',   # Right double quote
        "\u201e": '"',   # Double low-9 quote
        "\u201f": '"',   # Double high-reversed-9 quote
        "\u2013": "-",   # En dash
        "\u2014": "--",  # Em dash
        "\u2015": "--",  # Horizontal bar
        "\u2212": "-",   # Minus sign
        "\u2026": "...", # Horizontal ellipsis
        "\u2022": "*",   # Bullet
        "\u25e6": "*",   # White bullet
        "\u2023": "*",   # Triangular bullet
        "\u00b7": "*",   # Middle dot
        "\u25aa": "*",   # Black small square
        "\u25ab": "*",   # White small square
        "\u2264": "<=",  # Less than or equal to
        "\u2265": ">=",  # Greater than or equal to
        "\u2260": "!=",  # Not equal to
        "\u2248": "~",   # Almost equal to
        "\u00d7": "x",   # Multiplication sign
        "\u00f7": "/",   # Division sign
        "\u2192": "->",  # Right arrow
        "\u2190": "<-",  # Left arrow
        "\u200b": "",    # Zero-width space
        "\ufeff": "",    # Byte order mark
        "\u00a0": " ",   # Non-breaking space
        "\t": "    ",    # Tab to 4 spaces
        "\r": ""         # Carriage return
    }

    for unicode_char, ascii_replacement in replacements.items():
        text = text.replace(unicode_char, ascii_replacement)

    # Encode with replacement to guarantee zero crash on any unsupported character
    return text.encode("latin-1", "replace").decode("latin-1")


# ==============================================================================
# CSV Export Function
# ==============================================================================

def questions_to_csv(
    questions: List[QuestionItem],
    evaluation: Optional[EvaluationReport] = None
) -> bytes:
    """
    Exports questions, options, answer keys, explanations, and audit metrics
    to UTF-8 CSV bytes using pandas.

    Args:
        questions: List of QuestionItem objects.
        evaluation: Optional EvaluationReport object.

    Returns:
        bytes: UTF-8 encoded CSV file bytes.
    """
    eval_map = {}
    if evaluation and evaluation.evaluations:
        for ev in evaluation.evaluations:
            eval_map[ev.question_id] = ev

    records = []
    for q in questions:
        opt_a = q.options[0] if len(q.options) > 0 else ""
        opt_b = q.options[1] if len(q.options) > 1 else ""
        opt_c = q.options[2] if len(q.options) > 2 else ""
        opt_d = q.options[3] if len(q.options) > 3 else ""

        row = {
            "Question ID": q.id,
            "Type": q.question_type,
            "Bloom Level": q.bloom_level,
            "Difficulty": q.difficulty,
            "Question Text": q.question_text,
            "Option A": opt_a,
            "Option B": opt_b,
            "Option C": opt_c,
            "Option D": opt_d,
            "Correct Answer": q.correct_answer,
            "Explanation": q.explanation,
        }

        if q.id in eval_map:
            ev = eval_map[q.id]
            row["Factual Score (1-5)"] = ev.factual_correctness_score
            row["Distractor Score (1-5)"] = ev.distractor_quality_score
            row["Bloom Score (1-5)"] = ev.bloom_accuracy_score
            row["Judge Critique"] = ev.critique

        records.append(row)

    df = pd.DataFrame(records)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, encoding="utf-8")
    return csv_buffer.getvalue().encode("utf-8")


# ==============================================================================
# Custom FPDF Printable Document Class
# ==============================================================================

class AssessmentPDF(FPDF):
    """Clean, academic PDF document layout using fpdf2."""

    def __init__(self, assessment_title: str = "BloomQuiz Assessment"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.assessment_title = assessment_title
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        # Header banner on every page
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 116, 139)  # Slate
        self.cell(100, 6, sanitize_for_pdf(self.assessment_title[:45]), border=0, align="L")
        self.cell(0, 6, "BloomQuiz", border=0, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)  # Border gray
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        # Footer on every page
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}  |  Confidential Assessment", align="C")


# ==============================================================================
# PDF Export Function
# ==============================================================================

def questions_to_pdf(
    questions: List[QuestionItem],
    title: str = "BloomQuiz Assessment",
    evaluation: Optional[EvaluationReport] = None,
) -> bytes:
    """
    Generates a clean, publication-ready printable assessment PDF using fpdf2.
    Questions are listed first (Part I), and a dedicated Answer Key & Explanations
    section starts on a fresh page (Part II), followed by an optional Quality Audit (Part III).

    Args:
        questions: List of QuestionItem objects.
        title: Title of the assessment.
        evaluation: Optional LLM-as-a-judge EvaluationReport.

    Returns:
        bytes: Raw PDF bytes.
    """
    pdf = AssessmentPDF(assessment_title=title)
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- Title & Cover Header ---
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)  # Dark navy (#0f172a)
    pdf.multi_cell(0, 8, sanitize_for_pdf(title), align="C")
    pdf.ln(2)

    # Subtitle Metadata Bar
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(71, 85, 105)
    mcq_count = sum(1 for q in questions if q.question_type == "MCQ")
    sa_count = sum(1 for q in questions if q.question_type != "MCQ")
    meta_str = f"Total Questions: {len(questions)}  |  MCQ: {mcq_count}  |  Short Answer: {sa_count}"
    pdf.cell(0, 6, sanitize_for_pdf(meta_str), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Instructions Box
    pdf.set_fill_color(248, 250, 252)  # Off-white
    pdf.set_draw_color(203, 213, 225)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(51, 65, 85)
    instructions = (
        "Instructions: Read each question carefully. For Multiple Choice questions, mark the single best "
        "option. For Short Answer questions, write concise, precise answers in the space provided. "
        "The Answer Key and Grounded Explanations begin on a dedicated page in Part II."
    )
    pdf.multi_cell(0, 5, sanitize_for_pdf(instructions), border=1, fill=True, align="L")
    pdf.ln(6)

    # ==========================================================================
    # PART I: QUESTIONS
    # ==========================================================================
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 58, 138)  # Deep blue (#1e3a8a)
    pdf.cell(0, 8, "PART I: QUESTIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(30, 58, 138)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    opt_letters = ["A", "B", "C", "D"]

    for q in questions:
        # Check space remaining for question card
        if pdf.get_y() > 240:
            pdf.add_page()

        # Question Header Tag
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 41, 59)
        type_badge = f"[{q.question_type.upper()}]"
        meta_badge = f"Bloom: {q.bloom_level}  |  Difficulty: {q.difficulty}"
        pdf.cell(0, 6, f"Question {q.id}  {type_badge}  --  {meta_badge}", new_x="LMARGIN", new_y="NEXT")

        # Question Text
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(0, 5.5, sanitize_for_pdf(q.question_text))
        pdf.ln(2)

        # Render Options or Answer Lines
        if q.question_type == "MCQ" and q.options:
            pdf.set_font("Helvetica", "", 9.5)
            for idx, opt in enumerate(q.options[:4]):
                letter = opt_letters[idx] if idx < len(opt_letters) else f"({idx+1})"
                # Clean option text
                opt_clean = opt.strip()
                if opt_clean.startswith(f"{letter})") or opt_clean.startswith(f"{letter}."):
                    opt_display = opt_clean
                else:
                    opt_display = f"({letter})  {opt_clean}"
                
                pdf.set_x(18)
                pdf.multi_cell(0, 5, sanitize_for_pdf(opt_display))
            pdf.ln(3)
        else:
            # Short Answer: Render clean ruled dotted lines
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(148, 163, 184)
            pdf.cell(0, 4, "Answer space:", new_x="LMARGIN", new_y="NEXT")
            for _ in range(3):
                pdf.cell(0, 5, ". " * 52, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

        pdf.set_draw_color(241, 245, 249)
        pdf.line(12, pdf.get_y(), 198, pdf.get_y())
        pdf.ln(3)

    # ==========================================================================
    # PART II: ANSWER KEY & DETAILED EXPLANATIONS (DEDICATED PAGE)
    # ==========================================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(180, 83, 9)  # Amber / Dark orange (#b45309)
    pdf.cell(0, 8, "PART II: ANSWER KEY & DETAILED EXPLANATIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(180, 83, 9)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, "Official solutions and evidence-based explanations grounded strictly in the source.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    for q in questions:
        if pdf.get_y() > 240:
            pdf.add_page()

        # Question header
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, f"Q{q.id}. ({q.question_type})  {sanitize_for_pdf(q.question_text[:75])}...", new_x="LMARGIN", new_y="NEXT")

        # Correct Answer
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(22, 101, 52)  # Dark green (#166534)
        pdf.set_x(14)
        pdf.multi_cell(0, 5, sanitize_for_pdf(f"Correct Answer: {q.correct_answer}"))

        # Explanation
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(51, 65, 85)
        pdf.set_x(14)
        pdf.multi_cell(0, 4.8, sanitize_for_pdf(f"Explanation: {q.explanation}"))
        pdf.ln(3)

        pdf.set_draw_color(241, 245, 249)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(3)

    # ==========================================================================
    # PART III: QUALITY AUDIT REPORT (IF EVALUATION AVAILABLE)
    # ==========================================================================
    if evaluation and evaluation.evaluations:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(79, 70, 229)  # Indigo (#4f46e5)
        pdf.cell(0, 8, "PART III: LLM-AS-A-JUDGE QUALITY AUDIT", new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(79, 70, 229)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        # Overall Score Banner
        pdf.set_fill_color(238, 242, 255)  # Light indigo fill
        pdf.set_draw_color(199, 210, 254)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(49, 46, 129)
        score_summary = (
            f"Overall Quality Score: {evaluation.overall_quality_score:.2f} / 5.00  |  "
            f"Factual Correctness: {evaluation.factual_correctness_avg:.2f}  |  "
            f"Distractors: {evaluation.distractor_quality_avg:.2f}  |  "
            f"Bloom Accuracy: {evaluation.bloom_accuracy_avg:.2f}"
        )
        pdf.multi_cell(0, 7, sanitize_for_pdf(score_summary), border=1, fill=True, align="C")
        pdf.ln(3)

        if evaluation.summary:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(55, 65, 81)
            pdf.multi_cell(0, 5, sanitize_for_pdf(f"Executive Summary: {evaluation.summary}"))
            pdf.ln(3)

        # Per-question critiques
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, "Per-Question Audit Scores & Critiques:", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        for ev in evaluation.evaluations:
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(15, 23, 42)
            scores_line = (
                f"Question {ev.question_id}:  Factual: {ev.factual_correctness_score}/5  |  "
                f"Distractor: {ev.distractor_quality_score}/5  |  "
                f"Bloom Alignment: {ev.bloom_accuracy_score}/5"
            )
            pdf.cell(0, 5, scores_line, new_x="LMARGIN", new_y="NEXT")

            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(75, 85, 99)
            pdf.set_x(14)
            pdf.multi_cell(0, 4.5, sanitize_for_pdf(f"Critique: {ev.critique}"))
            pdf.ln(2)

    return bytes(pdf.output())
