"""
app.py
======
BloomQuiz — Turn any PDF or textbook chapter into smart, Bloom-aligned
practice quizzes in seconds.
"""

import os
import dotenv
import streamlit as st
import pymupdf
from generator import (
    generate_assessment,
    evaluate_questions,
    grade_short_answers,
    Assessment,
    EvaluationReport,
)
from exporter import questions_to_csv, questions_to_pdf

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
dotenv.load_dotenv()
api_key: str = os.getenv("GEMINI_API_KEY", "").strip()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BloomQuiz",
    page_icon=None,
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Global CSS — Modern SaaS Aesthetic (Dark Navy, Royal Purple, Emerald, Gold)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Hide Streamlit chrome & sidebar */
    #MainMenu, header, footer { display: none !important; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }

    /* Rich soft gradient page background */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #EDE9FE 0%, #E0E7FF 50%, #D1FAE5 100%);
    }

    /* Fit cleanly on a standard laptop screen */
    .block-container {
        max-width: 920px !important;
        padding-top: 1.1rem !important;
        padding-bottom: 2rem !important;
    }

    /* Compact, Punchy Hero Banner */
    .bq-hero {
        background: linear-gradient(120deg, #1E1B4B 0%, #4C1D95 58%, #6D28D9 100%);
        padding: 1.35rem 1.85rem;
        border-radius: 16px;
        margin-bottom: 1.1rem;
        box-shadow: 0 10px 25px rgba(30, 27, 75, 0.18);
        border-bottom: 4px solid #FBBF24;
    }
    .bq-title {
        font-size: 2.15rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        margin: 0 0 0.2rem 0;
        line-height: 1.15;
    }
    .bq-title span {
        color: #FBBF24;
    }
    .bq-subtitle {
        font-size: 1rem;
        font-weight: 500;
        color: #E0E7FF;
        margin: 0;
        line-height: 1.4;
    }

    /* Crisp White Elevated Control & Question Cards */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important;
        border-radius: 16px !important;
        border: 1px solid rgba(109, 40, 217, 0.18) !important;
        border-top: 4px solid #6D28D9 !important;
        box-shadow: 0 12px 30px rgba(30, 27, 75, 0.08) !important;
        padding: 0.35rem 0.5rem !important;
    }

    /* Larger, Slightly Bolder Labels & Input Text */
    [data-testid="stWidgetLabel"] p,
    .stCheckbox label p {
        font-size: 1.02rem !important;
        font-weight: 600 !important;
        color: #1E1B4B !important;
    }
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div {
        font-size: 1rem !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        background-color: #F8FAFC !important;
        border-radius: 10px !important;
        border: 1.5px solid #CBD5E1 !important;
    }
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="input"] > div:focus-within {
        border-color: #6D28D9 !important;
        background-color: #FFFFFF !important;
    }

    /* Styled File Dropzone */
    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(135deg, #F5F3FF 0%, #EEF2FF 100%) !important;
        border: 2px dashed #8B5CF6 !important;
        border-radius: 12px !important;
        padding: 0.85rem 1rem !important;
    }
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] small {
        font-weight: 600 !important;
        color: #312E81 !important;
    }

    /* Tighter horizontal dividers inside cards */
    hr {
        margin: 0.75rem 0 !important;
        border-color: #E2E8F0 !important;
    }

    /* Primary Button */
    button[kind="primary"] {
        background: linear-gradient(90deg, #6D28D9 0%, #4F46E5 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        font-size: 1.06rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.2px;
        padding: 0.65rem 1.25rem !important;
        box-shadow: 0 6px 18px rgba(109, 40, 217, 0.32) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 22px rgba(109, 40, 217, 0.42) !important;
    }

    /* Secondary & Download Buttons */
    .stDownloadButton button, button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #1E1B4B !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 10px !important;
        font-size: 0.96rem !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }
    .stDownloadButton button:hover, button[kind="secondary"]:hover {
        border-color: #6D28D9 !important;
        color: #6D28D9 !important;
        background: #F5F3FF !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.85);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #CBD5E1;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        color: #475569;
        padding: 0.45rem 1.1rem;
    }
    .stTabs [aria-selected="true"] {
        background: #6D28D9 !important;
        color: #FFFFFF !important;
    }

    /* Color-coded Pill Badges */
    .pill {
        display: inline-block;
        padding: 0.24rem 0.72rem;
        font-size: 0.76rem;
        font-weight: 700;
        border-radius: 9999px;
        margin-right: 0.4rem;
        margin-bottom: 0.45rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    .pill-mcq   { background: #D1FAE5; color: #065F46; }
    .pill-sa    { background: #CCFBF1; color: #0F766E; }
    .pill-bloom { background: #EDE9FE; color: #5B21B6; }
    .pill-diff  { background: #FEF3C7; color: #92400E; }

    /* Question Left Accent Bars */
    .q-accent-mcq {
        border-left: 5px solid #6D28D9;
        padding-left: 0.9rem;
        margin-bottom: 0.5rem;
    }
    .q-accent-sa {
        border-left: 5px solid #059669;
        padding-left: 0.9rem;
        margin-bottom: 0.5rem;
    }

    /* Answer Feedback Banners */
    .fb-correct {
        background: #ECFDF5;
        border-left: 4px solid #059669;
        color: #065F46;
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.5rem;
        font-size: 0.96rem;
        font-weight: 600;
    }
    .fb-partial {
        background: #FFFBEB;
        border-left: 4px solid #D97706;
        color: #92400E;
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.5rem;
        font-size: 0.96rem;
        font-weight: 600;
    }
    .fb-wrong {
        background: #FFF1F2;
        border-left: 4px solid #E11D48;
        color: #9F1239;
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.5rem;
        font-size: 0.96rem;
        font-weight: 600;
    }
    .fb-answer {
        background: #F8FAFC;
        border-left: 4px solid #6D28D9;
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.5rem;
        font-size: 0.96rem;
        font-weight: 500;
        color: #1E293B;
    }
    /* Full-Screen Centered Landing Hero */
    .bq-landing-wrap {
        margin-top: 8vh;
        text-align: center;
    }
    .bq-landing-card {
        background: linear-gradient(125deg, #1E1B4B 0%, #4C1D95 55%, #6D28D9 100%);
        padding: 3.5rem 2.75rem;
        border-radius: 22px;
        box-shadow: 0 20px 45px rgba(30, 27, 75, 0.22);
        border-bottom: 5px solid #FBBF24;
        margin-bottom: 1.75rem;
    }
    .bq-landing-title {
        font-size: 3.6rem;
        font-weight: 800;
        letter-spacing: -1px;
        color: #FFFFFF;
        margin: 0 0 0.75rem 0;
        line-height: 1.1;
    }
    .bq-landing-title span {
        color: #FBBF24;
    }
    .bq-landing-sub {
        font-size: 1.22rem;
        font-weight: 400;
        color: #E0E7FF;
        max-width: 620px;
        margin: 0 auto 1.75rem auto;
        line-height: 1.6;
    }
    .bq-landing-pills {
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 0.65rem;
    }
    .bq-landing-pill {
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(251, 191, 36, 0.45);
        color: #FEF3C7;
        padding: 0.4rem 1rem;
        border-radius: 9999px;
        font-size: 0.88rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Demo passage
# ---------------------------------------------------------------------------
DEMO_PASSAGE = """
Photosynthesis is a vital biological process used by plants, algae, and certain bacteria to
synthesize organic compounds from inorganic materials using solar energy. During oxygenic
photosynthesis, light energy transfers electrons from water (H2O) to carbon dioxide (CO2),
producing carbohydrates like glucose (C6H12O6) and releasing molecular oxygen (O2) as a
byproduct.

The process comprises two integrated phases: the Light-Dependent Reactions and the
Light-Independent Reactions (Calvin Cycle). The light-dependent reactions occur within the
thylakoid membranes of chloroplasts, where chlorophyll and other pigments capture photon
energy. Photosystem II (PSII) absorbs light at 680 nm, exciting electrons that split water
through photolysis into protons, electrons, and oxygen. These energized electrons traverse an
electron transport chain to Photosystem I (PSI, absorbing at 700 nm), generating ATP via
photophosphorylation and reducing NADP+ to NADPH.

The Calvin Cycle takes place in the stroma of the chloroplast. It utilizes the ATP and NADPH
generated by the light reactions to convert CO2 into glyceraldehyde-3-phosphate (G3P). The
critical enzyme catalyzing carbon fixation is RuBisCO, the most abundant enzyme on Earth.
RuBisCO fixes CO2 onto the 5-carbon sugar ribulose 1,5-bisphosphate (RuBP), yielding
unstable 6-carbon intermediates that split into 3-phosphoglycerate (3-PGA). The cycle
requires 9 ATP and 6 NADPH molecules for every net G3P molecule exported for glucose synthesis.
""".strip()


# ---------------------------------------------------------------------------
# PDF extraction helper
# ---------------------------------------------------------------------------
def extract_pdf_content(pdf_bytes: bytes, start_page: int, end_page: int):
    """
    Returns (text, images, is_scanned).
    Falls back to 110 DPI PNG images when extracted text < 50 chars.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    start_idx = max(0, start_page - 1)
    end_idx = min(doc.page_count, end_page)

    full_text = ""
    for pn in range(start_idx, end_idx):
        page = doc.load_page(pn)
        full_text += f"\n--- Page {pn + 1} ---\n{page.get_text() or ''}"

    cleaned = full_text.strip()

    if len(cleaned) < 50:
        images = []
        for pn in range(start_idx, end_idx):
            pix = doc.load_page(pn).get_pixmap(dpi=110)
            images.append(pix.tobytes("png"))
        return cleaned, images, True

    return cleaned[:8000], None, False


# ---------------------------------------------------------------------------
# API key guard
# ---------------------------------------------------------------------------
if not api_key:
    st.error(
        "GEMINI_API_KEY is not configured. "
        "Add it to the .env file in the project root and restart the app."
    )
    st.stop()


if "started" not in st.session_state:
    st.session_state.started = False

# ===========================================================================
# LANDING PAGE (Shown first until user clicks Start)
# ===========================================================================
if not st.session_state.started:
    st.markdown(
        """
        <div class="bq-landing-wrap">
            <div class="bq-landing-card">
                <div class="bq-landing-title">Bloom<span>Quiz</span></div>
                <div class="bq-landing-sub">
                    Turn any PDF or textbook chapter into smart, Bloom-aligned practice quizzes in seconds.
                </div>
                <div class="bq-landing-pills">
                    <span class="bq-landing-pill">Bloom's Taxonomy Calibrated</span>
                    <span class="bq-landing-pill">MCQ &amp; Short-Answer Mix</span>
                    <span class="bq-landing-pill">AI Grading &amp; Quality Audit</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1.2, 1.6, 1.2])
    with center_col:
        if st.button("Start Creating Quiz", type="primary", use_container_width=True):
            st.session_state.started = True
            st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for _k, _v in {
    "assessment": None,
    "evaluation": None,
    "extraction_info": None,
    "source_text": None,
    "source_images": None,
    "practice_submitted": False,
    "user_answers": {},
    "sa_grades": {},
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ===========================================================================
# CONTROL CARD
# ===========================================================================
with st.container(border=True):

    # --- Row 1: source ---
    use_demo = st.checkbox("Use sample passage (Photosynthesis)", value=False)
    uploaded_file = None

    if not use_demo:
        uploaded_file = st.file_uploader(
            "Upload PDF notes or textbook",
            type=["pdf"],
            label_visibility="visible",
        )

    start_page, end_page = 1, 1
    if uploaded_file and not use_demo:
        try:
            _doc = pymupdf.open(stream=uploaded_file.getvalue(), filetype="pdf")
            total_pages = max(1, _doc.page_count)
            pcol1, pcol2 = st.columns(2)
            with pcol1:
                start_page = st.number_input(
                    "Start Page", min_value=1, max_value=total_pages, value=1, step=1
                )
            with pcol2:
                end_page = st.number_input(
                    "End Page",
                    min_value=int(start_page),
                    max_value=total_pages,
                    value=min(total_pages, int(start_page) + 2),
                    step=1,
                )
            st.caption(f"Document: {total_pages} pages total")
        except Exception as _e:
            st.error(f"Could not read PDF: {_e}")

    st.markdown("---")

    # --- Row 2: parameters ---
    col_diff, col_bloom, col_mcq, col_sa = st.columns([1.15, 1.25, 1, 1])

    with col_diff:
        difficulty = st.selectbox(
            "Difficulty",
            ["Easy", "Medium", "Hard"],
            index=1,
        )

    with col_bloom:
        bloom_level = st.selectbox(
            "Bloom's Level",
            ["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"],
            index=2,
        )

    with col_mcq:
        mcq_count = st.number_input("MCQs", min_value=0, max_value=15, value=3, step=1)

    with col_sa:
        sa_count = st.number_input("Short Answer", min_value=0, max_value=15, value=2, step=1)

    total_q = int(mcq_count) + int(sa_count)
    if total_q > 0:
        st.caption(f"{total_q} questions selected")

    # --- Row 3: generate button ---
    _source_ready = use_demo or (uploaded_file is not None)
    generate_btn = st.button(
        "Generate Quiz",
        type="primary",
        disabled=(total_q == 0 or not _source_ready),
        use_container_width=True,
    )


# ===========================================================================
# GENERATION PIPELINE (Clean single spinner — zero verbose logs)
# ===========================================================================
if generate_btn:
    st.session_state.practice_submitted = False
    st.session_state.user_answers = {}
    st.session_state.sa_grades = {}
    st.session_state.evaluation = None

    with st.spinner("Crafting your quiz..."):
        try:
            if use_demo:
                source_text = DEMO_PASSAGE[:8000]
                source_images = None
                st.session_state.extraction_info = {
                    "chars": len(source_text),
                    "is_scanned": False,
                    "pages": "sample passage",
                }
            else:
                _raw, _imgs, _scanned = extract_pdf_content(
                    uploaded_file.getvalue(), int(start_page), int(end_page)
                )
                if _scanned:
                    source_text = None
                    source_images = _imgs
                    st.session_state.extraction_info = {
                        "images_count": len(_imgs),
                        "is_scanned": True,
                        "pages": f"{start_page}-{end_page}",
                    }
                else:
                    source_text = _raw
                    source_images = None
                    st.session_state.extraction_info = {
                        "chars": len(source_text),
                        "is_scanned": False,
                        "pages": f"{start_page}-{end_page}",
                    }

            st.session_state.source_text = source_text
            st.session_state.source_images = source_images

            assessment = generate_assessment(
                api_key=api_key,
                source_text=source_text,
                source_images=source_images,
                difficulty=difficulty,
                bloom_level=bloom_level,
                mcq_count=int(mcq_count),
                short_answer_count=int(sa_count),
                model_name="gemini-3.8-flash",
            )
            st.session_state.assessment = assessment

        except Exception as _e:
            st.error(str(_e))


# ===========================================================================
# RESULTS
# ===========================================================================
if st.session_state.assessment and st.session_state.assessment.questions:
    assessment: Assessment = st.session_state.assessment
    evaluation: EvaluationReport | None = st.session_state.evaluation

    # --- Action Toolbar ---
    csv_bytes = questions_to_csv(assessment.questions, evaluation)
    pdf_bytes = questions_to_pdf(assessment.questions, assessment.title, evaluation)

    _safe_title = assessment.title.lower().replace(" ", "_")
    tb1, tb2, tb3 = st.columns(3)
    with tb1:
        st.download_button(
            "Export PDF",
            data=pdf_bytes,
            file_name=f"{_safe_title}_quiz.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with tb2:
        st.download_button(
            "Export CSV",
            data=csv_bytes,
            file_name=f"{_safe_title}_questions.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with tb3:
        run_qc = st.button("Run Quality Check", use_container_width=True)

    # On-demand quality evaluation
    if run_qc:
        with st.spinner("Running quality audit..."):
            try:
                evaluation = evaluate_questions(
                    api_key=api_key,
                    questions=assessment.questions,
                    source_text=st.session_state.source_text,
                    source_images=st.session_state.source_images,
                    model_name="gemini-3.8-flash",
                )
                st.session_state.evaluation = evaluation
                st.rerun()
            except Exception as _qc_err:
                st.error(str(_qc_err))

    st.markdown("")

    # -----------------------------------------------------------------------
    # Tabs
    # -----------------------------------------------------------------------
    tab_practice, tab_answers, tab_quality = st.tabs(
        ["Practice Quiz", "Answer Key", "Quality Report"]
    )

    # =========================================================
    # TAB 1 — PRACTICE QUIZ
    # =========================================================
    with tab_practice:
        with st.form("quiz_form"):
            user_inputs: dict = {}
            for q in assessment.questions:
                with st.container(border=True):
                    _is_mcq = q.question_type == "MCQ"
                    _type_cls = "pill-mcq" if _is_mcq else "pill-sa"
                    _accent_cls = "q-accent-mcq" if _is_mcq else "q-accent-sa"

                    st.markdown(
                        f'<div class="{_accent_cls}">'
                        f'<span class="pill {_type_cls}">{q.question_type}</span>'
                        f'<span class="pill pill-bloom">{q.bloom_level}</span>'
                        f'<span class="pill pill-diff">{q.difficulty}</span>'
                        f'<div style="font-weight:700; color:#0F172A; font-size:1.03rem; margin-top:0.2rem;">'
                        f'{q.id}. {q.question_text}</div></div>',
                        unsafe_allow_html=True,
                    )

                    if _is_mcq and q.options:
                        user_inputs[q.id] = st.radio(
                            f"q{q.id}",
                            q.options,
                            index=None,
                            key=f"r_{q.id}",
                            label_visibility="collapsed",
                        )
                    else:
                        user_inputs[q.id] = st.text_area(
                            f"q{q.id}",
                            placeholder="Write your answer here...",
                            key=f"t_{q.id}",
                            height=90,
                            label_visibility="collapsed",
                        )

            submitted = st.form_submit_button("Submit Answers", type="primary", use_container_width=True)

        if submitted:
            st.session_state.practice_submitted = True
            st.session_state.user_answers = user_inputs

            # Grade Short-Answer responses with AI
            sa_submissions = [
                {
                    "question_id": q.id,
                    "question": q.question_text,
                    "model_answer": q.correct_answer,
                    "student_answer": (user_inputs.get(q.id) or "").strip(),
                }
                for q in assessment.questions
                if q.question_type != "MCQ"
            ]
            if sa_submissions:
                with st.spinner("Evaluating your responses..."):
                    try:
                        st.session_state.sa_grades = grade_short_answers(
                            api_key=api_key,
                            submissions=sa_submissions,
                            model_name="gemini-3.8-flash",
                        )
                    except Exception:
                        st.session_state.sa_grades = {}

        if st.session_state.practice_submitted:
            ua = st.session_state.user_answers
            sa_grades = st.session_state.sa_grades

            total_possible = float(len(assessment.questions))
            earned_score = 0.0

            for q in assessment.questions:
                if q.question_type == "MCQ":
                    if ua.get(q.id) == q.correct_answer:
                        earned_score += 1.0
                else:
                    g = sa_grades.get(q.id)
                    if g:
                        earned_score += g.score

            st.metric("Total Score", f"{earned_score:g} / {total_possible:g}")

            st.markdown("#### Detailed Review")
            for q in assessment.questions:
                ans = ua.get(q.id) or ""
                with st.container(border=True):
                    st.markdown(f"**{q.id}. {q.question_text}**")
                    if q.question_type == "MCQ":
                        if ans == q.correct_answer:
                            st.markdown(
                                f'<div class="fb-correct">Correct — {ans}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                f'<div class="fb-wrong">Incorrect. '
                                f'Your answer: {ans or "(none)"} &nbsp;|&nbsp; '
                                f'Correct answer: {q.correct_answer}</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        g = sa_grades.get(q.id)
                        st.markdown(
                            f'<div class="fb-answer">'
                            f'Your response: {ans.strip() or "(no answer)"}'
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        if g:
                            if g.verdict == "Correct":
                                st.markdown(
                                    f'<div class="fb-correct">Correct ({g.score:g}/1) — {g.feedback}<br>'
                                    f'<strong>Model answer:</strong> {q.correct_answer}</div>',
                                    unsafe_allow_html=True,
                                )
                            elif g.verdict == "Partial":
                                st.markdown(
                                    f'<div class="fb-partial">Partially Correct ({g.score:g}/1) — {g.feedback}<br>'
                                    f'<strong>Model answer:</strong> {q.correct_answer}</div>',
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f'<div class="fb-wrong">Incorrect (0/1) — {g.feedback}<br>'
                                    f'<strong>Model answer:</strong> {q.correct_answer}</div>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown(
                                f'<div class="fb-answer"><strong>Model answer:</strong> {q.correct_answer}</div>',
                                unsafe_allow_html=True,
                            )

                    with st.expander("View explanation"):
                        st.write(q.explanation)

    # =========================================================
    # TAB 2 — ANSWER KEY
    # =========================================================
    with tab_answers:
        st.markdown(f"#### {assessment.title}")
        if assessment.topic_summary:
            st.write(assessment.topic_summary)

        filter_col, _ = st.columns([1, 2])
        with filter_col:
            filter_type = st.radio(
                "Show",
                ["All", "MCQ only", "Short Answer only"],
                horizontal=True,
                label_visibility="collapsed",
            )

        for q in assessment.questions:
            if filter_type == "MCQ only" and q.question_type != "MCQ":
                continue
            if filter_type == "Short Answer only" and q.question_type == "MCQ":
                continue

            with st.container(border=True):
                _is_mcq = q.question_type == "MCQ"
                _tc = "pill-mcq" if _is_mcq else "pill-sa"
                _ac = "q-accent-mcq" if _is_mcq else "q-accent-sa"

                st.markdown(
                    f'<div class="{_ac}">'
                    f'<span class="pill {_tc}">{q.question_type}</span>'
                    f'<span class="pill pill-bloom">{q.bloom_level}</span>'
                    f'<span class="pill pill-diff">{q.difficulty}</span>'
                    f'<div style="font-weight:700; color:#0F172A; font-size:1.03rem; margin-top:0.2rem;">'
                    f'{q.id}. {q.question_text}</div></div>',
                    unsafe_allow_html=True,
                )

                if _is_mcq and q.options:
                    for oi, opt in enumerate(q.options):
                        letter = chr(65 + oi)
                        is_correct = opt == q.correct_answer
                        marker = "**" if is_correct else ""
                        check = " (correct)" if is_correct else ""
                        st.markdown(f"- {marker}({letter}) {opt}{check}{marker}")

                st.markdown(
                    f'<div class="fb-correct">Answer: {q.correct_answer}</div>',
                    unsafe_allow_html=True,
                )
                with st.expander("Explanation"):
                    st.write(q.explanation)

    # =========================================================
    # TAB 3 — QUALITY REPORT
    # =========================================================
    with tab_quality:
        st.markdown("#### Quality Report")

        if evaluation:
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("Overall", f"{evaluation.overall_quality_score:.1f} / 5.0")
            with k2:
                st.metric("Factual", f"{evaluation.factual_correctness_avg:.1f} / 5.0")
            with k3:
                st.metric("Distractors", f"{evaluation.distractor_quality_avg:.1f} / 5.0")
            with k4:
                st.metric("Bloom Fit", f"{evaluation.bloom_accuracy_avg:.1f} / 5.0")

            st.markdown("---")
            for label, val in [
                ("Factual Correctness", evaluation.factual_correctness_avg),
                ("Distractor Quality", evaluation.distractor_quality_avg),
                ("Bloom Alignment", evaluation.bloom_accuracy_avg),
            ]:
                st.caption(f"{label}: {val:.1f} / 5.0")
                st.progress(val / 5.0)

            if evaluation.summary:
                st.info(evaluation.summary)

            st.markdown("---")
            st.markdown("**Per-question breakdown**")

            eval_map = {ev.question_id: ev for ev in evaluation.evaluations}
            for q in assessment.questions:
                ev = eval_map.get(q.id)
                _avg = (
                    round(
                        (ev.factual_correctness_score + ev.distractor_quality_score + ev.bloom_accuracy_score)
                        / 3,
                        1,
                    )
                    if ev
                    else "—"
                )
                with st.expander(f"Question {q.id} — Score: {_avg} / 5.0"):
                    st.write(f"**Question:** {q.question_text}")
                    if ev:
                        sc1, sc2, sc3 = st.columns(3)
                        with sc1:
                            st.metric("Factual", f"{ev.factual_correctness_score} / 5")
                        with sc2:
                            st.metric("Distractors", f"{ev.distractor_quality_score} / 5")
                        with sc3:
                            st.metric("Bloom Fit", f"{ev.bloom_accuracy_score} / 5")
                        st.caption(f"Note: {ev.critique}")

            st.markdown("---")
            if st.button("Re-run Quality Check"):
                with st.spinner("Re-running quality audit..."):
                    try:
                        new_eval = evaluate_questions(
                            api_key=api_key,
                            questions=assessment.questions,
                            source_text=st.session_state.source_text,
                            source_images=st.session_state.source_images,
                            model_name="gemini-3.8-flash",
                        )
                        st.session_state.evaluation = new_eval
                        st.rerun()
                    except Exception as _re_err:
                        st.error(str(_re_err))

        else:
            st.info(
                "Quality analysis has not been run yet. "
                "Click 'Run Quality Check' above the tabs to audit this quiz."
            )