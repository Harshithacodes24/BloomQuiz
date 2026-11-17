# 🎓 AI Assessment Studio
### Project B17: Automatic Question Generation & LLM-as-a-Judge Evaluation

AI Assessment Studio is an enterprise-grade, pedagogically grounded assessment generation and evaluation web application built with Python, Streamlit, and Google's official `google-genai` SDK powered by **Gemini 3.8 Flash**.

---

## 🌟 Key Features

### 1. 📑 Hybrid PDF Extraction & Scanned Document Fallback
- **Direct Text Extraction**: High-performance text parsing across user-specified page ranges using PyMuPDF (`pymupdf`).
- **Scanned PDF Fallback**: If extracted text contains fewer than 50 characters (indicating a scanned document or image-only PDF), the application automatically renders the selected pages as PNG images at **110 DPI** (`get_pixmap(dpi=110)`) and routes them directly to Gemini's multimodal vision API. Text inputs are trimmed to 8,000 characters for optimal latency.

### 2. 🎯 Configurable Pedagogical Generation
- Powered by the official `google-genai` SDK (`from google import genai`) with model `gemini-3.8-flash`.
- **Strict Pydantic JSON Schema (`response_schema`)**: Guarantees zero parsing failures and strictly formatted output.
- **Cognitive Depth (Bloom's Taxonomy)**: Selectable levels — *Remember*, *Understand*, *Apply*, *Analyze*, *Evaluate*, and *Create*.
- **Configurable Difficulty**: *Easy*, *Medium*, or *Hard*.
- **Custom Question Mix**:
  - **Multiple Choice Questions (MCQ)**: Exactly 4 distinct plausible options, verbatim `correct_answer` match, strictly free of meta-choices like "All of the above" or "None of the above".
  - **Short Answer Questions**: Empty options list `[]` with an authoritative 2–3 sentence reference model answer.
  - **Evidence-Based Explanations**: Every question includes a thorough pedagogical explanation grounded strictly in the provided source material.

### 3. ⚖️ LLM-as-a-Judge Quality Audit
- Independent second-stage evaluation function (`evaluate_questions()`) using Pydantic's `EvaluationReport` schema.
- Audits every generated question against the source text/images and scores it from 1 to 5 on:
  - **Factual Correctness Score (1–5)**: Grounding and accuracy against source material.
  - **Distractor Quality Score (1–5)**: Subtlety, plausibility, and distinctness of MCQ distractors (defaults to 5 for Short Answer).
  - **Bloom Accuracy Score (1–5)**: Fidelity to the targeted cognitive depth.
  - **Per-Question Critique**: One-sentence actionable critique highlighting strengths or defects.
  - **Overall Quality Score**: Mathematical average across all criteria and questions out of 5.0.

### 4. 🖨️ Publication-Ready PDF & CSV Exports
- **Printable Assessment PDF (`fpdf2`)**:
  - **Part I**: Complete question paper with MCQ options and ruled dotted lines for short answer responses.
  - **Part II**: Dedicated **Answer Key & Detailed Explanations** section starting on a new page.
  - **Part III**: Quality audit breakdown and judge critiques.
  - **Unicode Sanitization**: Robust Latin-1 character conversion (em-dashes, curly quotes, bullets, math symbols) ensuring `fpdf2` never encounters `UnicodeEncodeError`.
- **Structured CSV Export (`pandas`)**: Clean UTF-8 CSV containing question IDs, types, Bloom levels, difficulties, prompts, options A–D, correct answers, explanations, and audit metrics.

### 5. 📝 Interactive Practice & Real-Time Grading
- Built-in interactive quiz environment with radio buttons and text areas.
- Instant automated scoring for MCQs with celebration animations for perfect scores.
- Side-by-side comparison with reference model answers for Short Answer questions.

---

## 📂 Project Structure

```
d:/Automatic_Question_Generator/
├── app.py              # Main Streamlit web application & UI
├── generator.py        # Gemini 3.8 Flash assessment generator & LLM judge
├── exporter.py         # PDF (fpdf2) and CSV (pandas) generation module
├── requirements.txt    # Project dependencies
├── .env.example        # Environment variable template
├── .env                # Local API key configuration (user provided)
└── README.md           # Documentation & user manual
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Google AI Studio API key ([Get a Gemini API Key](https://aistudio.google.com/))

### 1. Clone or Open the Workspace
```bash
cd d:/Automatic_Question_Generator
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Your API Key
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and insert your Gemini API Key:
```env
GEMINI_API_KEY=AIzaSy...your_actual_key_here
```
*(Alternatively, you can enter your API key directly in the application's sidebar interface.)*

---

## 🏃 Running the Application

Launch the Streamlit app with:
```bash
streamlit run app.py
```

The application will start and open automatically in your browser at:
```
http://localhost:8501
```

---

## 📖 How to Use AI Assessment Studio

1. **Configure API Key**: Ensure your Gemini API Key is entered in `.env` or in the sidebar.
2. **Select Source Document**:
   - Upload any academic PDF textbook, notes, or research paper, OR
   - Check **"Use Built-in Demo Passage"** to test immediately with the included Photosynthesis chapter.
3. **Choose Page Range**: Specify the `Start Page` and `End Page` to extract from.
4. **Set Pedagogical Controls**:
   - Select Difficulty: `Easy`, `Medium`, or `Hard`.
   - Select Bloom's Taxonomy Level: `Remember`, `Understand`, `Apply`, `Analyze`, `Evaluate`, or `Create`.
   - Adjust the sliders for desired counts of **MCQs** and **Short Answer** questions.
5. **Generate & Evaluate**: Click `🚀 Generate & Evaluate`.
6. **Interact & Export**:
   - **Download Exports**: Click **📄 Download Assessment PDF** or **📊 Download CSV** at the top.
   - **Interactive Practice**: Take the test interactively in the first tab and submit for instant scoring.
   - **Answers & Explanations**: Review the full structured answer key with evidence citations.
   - **Quality Evaluation Report**: Inspect the LLM judge's psychometric scores, summary, and per-question critiques.

---

## 🛠️ Tech Stack
- **Framework**: [Streamlit](https://streamlit.io/)
- **LLM Engine**: [Google GenAI SDK](https://github.com/google-gemini/google-genai) (`google-genai`, Gemini 3.8 Flash)
- **PDF Engine**: [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`)
- **PDF Generation**: [fpdf2](https://py-pdf.github.io/fpdf2/)
- **Data Modeling & Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Data Export**: [pandas](https://pandas.pydata.org/)
