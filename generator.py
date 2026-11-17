"""
generator.py
============
Assessment generation, LLM-as-a-judge quality evaluation, and short-answer
grading module powered by the official google-genai SDK and Gemini 3.8 Flash.
"""

import json
import time
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ==============================================================================
# Pydantic Schemas for Structured JSON Output
# ==============================================================================

class QuestionItem(BaseModel):
    """Schema for a single assessment question (MCQ or Short Answer)."""
    id: int = Field(
        description="Sequential unique integer ID of the question starting at 1"
    )
    question_type: Literal["MCQ", "Short Answer"] = Field(
        description="Format of the question: 'MCQ' or 'Short Answer'"
    )
    bloom_level: str = Field(
        description="Target Bloom's Taxonomy cognitive level (Remember, Understand, Apply, Analyze, Evaluate, Create)"
    )
    difficulty: str = Field(
        description="Target difficulty level (Easy, Medium, Hard)"
    )
    question_text: str = Field(
        description="Clear, well-articulated, unambiguous question prompt strictly grounded in the source"
    )
    options: List[str] = Field(
        default_factory=list,
        description=(
            "For MCQ: Exactly 4 distinct plausible options. "
            "For Short Answer: Must be an empty list []. "
            "CRITICAL: Never include 'All of the above', 'None of the above', or combined choices like 'Both A and B'."
        )
    )
    correct_answer: str = Field(
        description=(
            "For MCQ: Must be an EXACT verbatim match to one of the 4 strings in options. "
            "For Short Answer: Authoritative, concise 2-3 sentence reference model answer grounded strictly in the source."
        )
    )
    explanation: str = Field(
        description=(
            "Detailed pedagogical explanation strictly grounded in the provided source material, "
            "explaining why the answer is correct and why other choices are incorrect (for MCQ)."
        )
    )


class Assessment(BaseModel):
    """Schema for the complete generated assessment."""
    title: str = Field(
        default="AI Assessment",
        description="A concise, descriptive title for this assessment based on the covered topic"
    )
    topic_summary: str = Field(
        default="",
        description="A 2-3 sentence summary of the key concepts and scope covered from the source material"
    )
    questions: List[QuestionItem] = Field(
        default_factory=list,
        description="List of questions strictly matching the requested counts and Bloom/difficulty specifications"
    )


class QuestionEvaluation(BaseModel):
    """Schema for LLM-as-a-judge evaluation of a single question."""
    question_id: int = Field(
        description="ID of the question being audited"
    )
    question_type: str = Field(
        default="MCQ",
        description="Format of the question ('MCQ' or 'Short Answer')"
    )
    factual_correctness_score: int = Field(
        ge=1, le=5,
        description="Score 1-5: Factual accuracy and strict grounding in source material (5=flawless, 1=unsupported/hallucinated)"
    )
    distractor_quality_score: int = Field(
        ge=1, le=5,
        description="Score 1-5: Plausibility, distinctness, and non-triviality of distractors (default to 5 for Short Answer)"
    )
    bloom_accuracy_score: int = Field(
        ge=1, le=5,
        description="Score 1-5: How faithfully the question assesses the targeted Bloom's Taxonomy cognitive level"
    )
    critique: str = Field(
        description="One concise sentence auditing question clarity, pedagogical quality, and grounding in source"
    )


class EvaluationReport(BaseModel):
    """Schema for the overall LLM-as-a-judge audit report."""
    overall_quality_score: float = Field(
        description="Average quality score across all questions and criteria out of 5.0"
    )
    factual_correctness_avg: float = Field(
        default=5.0,
        description="Average factual correctness score out of 5.0"
    )
    distractor_quality_avg: float = Field(
        default=5.0,
        description="Average distractor quality score out of 5.0"
    )
    bloom_accuracy_avg: float = Field(
        default=5.0,
        description="Average Bloom's accuracy score out of 5.0"
    )
    summary: str = Field(
        default="",
        description="A 2-3 sentence executive evaluation summary explaining the assessment's validity and pedagogical rigor"
    )
    evaluations: List[QuestionEvaluation] = Field(
        default_factory=list,
        description="Individual evaluation scores and critiques for each question"
    )


class ShortAnswerGrade(BaseModel):
    """Schema for grading a single student short-answer submission."""
    question_id: int
    verdict: Literal["Correct", "Partial", "Incorrect"]
    score: float = Field(description="1.0 for Correct, 0.5 for Partial, 0.0 for Incorrect.")
    feedback: str = Field(description="One concise sentence explaining why the student earned this score.")


class ShortAnswerBatchReport(BaseModel):
    """Schema for batch short-answer grading results."""
    grades: List[ShortAnswerGrade]


# ==============================================================================
# Fast Flash-Only Model Discovery, Retries & Failover
# ==============================================================================

_model_candidates_cache: Optional[List[str]] = None
_known_404_models: set = set()


def _create_client(api_key: str) -> genai.Client:
    """Creates a Gemini client with a strict 25-second timeout so calls never hang."""
    return genai.Client(api_key=api_key, http_options={"timeout": 25000})


def _get_error_details(e: Exception) -> tuple[Optional[int], str]:
    """Extracts status code and lowercased error message from exception."""
    code = getattr(e, "code", None)
    if code is None:
        resp = getattr(e, "response", None)
        if resp is not None:
            code = getattr(resp, "status_code", None)
    msg = str(e).lower()
    return code, msg


def _is_transient_error(code: Optional[int], msg: str) -> bool:
    """Checks for 503, 429, or network timeout errors."""
    if code in (429, 503, 504):
        return True
    return any(indicator in msg for indicator in [
        "503", "429", "504", "unavailable", "resource_exhausted",
        "rate_limit", "rate limit", "overloaded", "quota", "timeout", "deadline"
    ])


def _is_not_found_error(code: Optional[int], msg: str) -> bool:
    """Checks for 404 (NOT_FOUND / Model Not Found)."""
    if code == 404:
        return True
    return "404" in msg or "not found" in msg or "not_found" in msg


def _discover_generate_models(client: genai.Client, preferred_model: str = "gemini-3.8-flash") -> List[str]:
    """
    Dynamically discovers live Flash models using client.models.list().
    Excludes slow Pro, audio, image, and TTS models for low-latency responses.
    """
    global _model_candidates_cache, _known_404_models

    if _model_candidates_cache is not None:
        return [m for m in _model_candidates_cache if m not in _known_404_models]

    candidates: List[str] = [preferred_model]
    try:
        for m in client.models.list():
            clean_name = (getattr(m, "name", "") or "").replace("models/", "").strip()
            if not clean_name:
                continue

            actions = getattr(m, "supported_actions", None) or []
            supports_generate = "generateContent" in actions or any(
                "generatecontent" in str(a).lower() for a in actions
            )

            c_lower = clean_name.lower()
            if (
                supports_generate
                and "flash" in c_lower
                and not any(x in c_lower for x in ["image", "audio", "tts", "robotics", "computer"])
                and clean_name not in candidates
            ):
                candidates.append(clean_name)
    except Exception as e:
        print(f"[BloomQuiz] Model list error: {e}")

    print(f"[BloomQuiz] Active Flash models: {candidates}")
    _model_candidates_cache = candidates
    return [m for m in candidates if m not in _known_404_models]


def _call_gemini_with_retry(
    client: genai.Client,
    model_name: str,
    contents: list,
    config: types.GenerateContentConfig,
    backoffs: tuple = (1,),
) -> types.GenerateContentResponse:
    """
    Executes client.models.generate_content with cached Flash model discovery,
    fast failover on timeout/503/429, and live terminal logging.
    """
    global _known_404_models

    candidates = _discover_generate_models(client, preferred_model=model_name or "gemini-3.8-flash")
    last_exception = None

    for current_model in candidates:
        if current_model in _known_404_models:
            continue

        print(f"[BloomQuiz] Calling model: {current_model}...")
        for attempt, delay in enumerate(backoffs):
            try:
                res = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=config,
                )
                print(f"[BloomQuiz] Success with {current_model}!")
                return res
            except Exception as e:
                last_exception = e
                code, msg = _get_error_details(e)
                print(f"[BloomQuiz] {current_model} failed ({code}): {msg[:120]}")

                if _is_not_found_error(code, msg):
                    _known_404_models.add(current_model)
                    break

                if _is_transient_error(code, msg):
                    if attempt < len(backoffs) - 1:
                        time.sleep(delay)
                    else:
                        break
                else:
                    raise e

    if last_exception:
        raise last_exception
    raise RuntimeError("All candidate Gemini Flash models failed to generate content.")


call_gemini_with_retry = _call_gemini_with_retry
is_retryable_error = lambda e: _is_transient_error(*_get_error_details(e))


# ==============================================================================
# Core Assessment Generation Function
# ==============================================================================

def generate_assessment(
    api_key: str,
    source_text: Optional[str] = None,
    source_images: Optional[List[bytes]] = None,
    difficulty: str = "Medium",
    bloom_level: str = "Apply",
    mcq_count: int = 3,
    short_answer_count: int = 2,
    model_name: str = "gemini-3.8-flash",
) -> Assessment:
    """
    Generates a structured assessment containing MCQs and Short Answer questions
    using Gemini 3.8 Flash and Pydantic response_schema.
    """
    if not api_key:
        raise ValueError("Gemini API key is required. Please check your .env file.")

    total_requested = mcq_count + short_answer_count
    if total_requested <= 0:
        raise ValueError("At least one question (MCQ or Short Answer) must be requested.")

    client = _create_client(api_key)

    generation_prompt = f"""
You are an expert psychometrician and university professor designing an academic assessment.
Your task is to generate exactly {total_requested} questions based STRICTLY and ONLY on the provided source material:
- Multiple Choice Questions (MCQ): {mcq_count}
- Short Answer Questions: {short_answer_count}

Target Specifications:
- Difficulty Level: {difficulty}
- Bloom's Taxonomy Cognitive Level: {bloom_level}

Strict Rules:
1. Grounding: Every question, answer, option, and explanation MUST be directly derived from and supported by the source material. Do NOT introduce external concepts not mentioned or implied in the source.
2. MCQ Rules:
   - Provide exactly 4 distinct, plausible options.
   - The 'correct_answer' MUST match one of the 4 options EXACTLY (verbatim match).
   - NEVER use 'All of the above', 'None of the above', 'Both A and B', or similar meta-options.
   - Distractors must be plausible misconceptions, not obviously absurd answers.
3. Short Answer Rules:
   - The 'options' list MUST be empty: [].
   - The 'correct_answer' MUST be a high-quality 2-3 sentence reference model answer grounded in the source.
4. Explanations:
   - Every question must include a thorough explanation referencing specific facts, definitions, or statements from the source.
5. Cognitive Alignment:
   - Ensure the questions authentically challenge the student at the '{bloom_level}' cognitive level.
"""

    contents = []
    if source_images and len(source_images) > 0:
        for img_bytes in source_images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        contents.append(
            types.Part.from_text(
                text=f"{generation_prompt}\n\n[Source Material: Please read and analyze the attached {len(source_images)} page image(s) above.]"
            )
        )
    else:
        text_content = (source_text or "")[:8000]
        contents.append(
            types.Part.from_text(
                text=f"{generation_prompt}\n\n### Source Material:\n{text_content}"
            )
        )

    response = _call_gemini_with_retry(
        client=client,
        model_name=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Assessment,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        ),
        backoffs=(1,),
    )

    raw_json = response.text or "{}"
    assessment = Assessment.model_validate_json(raw_json)

    # Post-validation sanitization & enforcement
    sanitized_questions: List[QuestionItem] = []
    for idx, q in enumerate(assessment.questions, start=1):
        q.id = idx
        q.bloom_level = q.bloom_level or bloom_level
        q.difficulty = q.difficulty or difficulty

        if q.question_type == "MCQ":
            cleaned_opts = [
                opt.strip() for opt in q.options
                if opt and not any(meta in opt.lower() for meta in ["all of the above", "none of the above"])
            ]
            while len(cleaned_opts) < 4:
                cleaned_opts.append(f"Alternative Option {len(cleaned_opts) + 1}")
            cleaned_opts = cleaned_opts[:4]
            q.options = cleaned_opts

            if q.correct_answer not in q.options:
                matched = False
                for opt in q.options:
                    if opt.lower() in q.correct_answer.lower() or q.correct_answer.lower() in opt.lower():
                        q.correct_answer = opt
                        matched = True
                        break
                if not matched:
                    q.correct_answer = q.options[0]
        else:
            q.question_type = "Short Answer"
            q.options = []

        sanitized_questions.append(q)

    assessment.questions = sanitized_questions
    return assessment


# ==============================================================================
# LLM-as-a-Judge Quality Evaluation Function
# ==============================================================================

def evaluate_questions(
    api_key: str,
    questions: List[QuestionItem],
    source_text: Optional[str] = None,
    source_images: Optional[List[bytes]] = None,
    model_name: str = "gemini-3.8-flash",
) -> EvaluationReport:
    """
    Independent LLM-as-a-Judge function that audits every generated question
    against the source text/images.
    """
    if not api_key:
        raise ValueError("Gemini API key is required for evaluation.")

    if not questions:
        return EvaluationReport(
            overall_quality_score=5.0,
            factual_correctness_avg=5.0,
            distractor_quality_avg=5.0,
            bloom_accuracy_avg=5.0,
            summary="No questions provided for evaluation.",
            evaluations=[]
        )

    client = _create_client(api_key)

    questions_dump = [
        {
            "question_id": q.id,
            "question_type": q.question_type,
            "bloom_level": q.bloom_level,
            "difficulty": q.difficulty,
            "question_text": q.question_text,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation
        }
        for q in questions
    ]

    judge_prompt = f"""
You are an expert psychometric judge, quality auditor, and curriculum reviewer (LLM-as-a-Judge).
Your task is to independently audit the following {len(questions)} generated assessment questions against the provided source material.

Audit Criteria for each question (score strictly from 1 to 5 as an integer):
1. 'factual_correctness_score' (1-5):
   - 5: Entirely accurate, precisely grounded in source text, no hallucination.
   - 3: Partially supported or contains slight ambiguity.
   - 1: Factually inaccurate, contradicts source, or completely unsupported.

2. 'distractor_quality_score' (1-5):
   - For MCQ: Evaluate whether the 3 distractors are plausible, non-trivial, distinct, and free of giveaway clues. (5=excellent distractors, 1=obvious nonsense or duplicate choices).
   - For Short Answer: MUST default to 5.

3. 'bloom_accuracy_score' (1-5):
   - Evaluate whether the question genuinely measures the cognitive depth specified by its targeted Bloom's Taxonomy level (Remember, Understand, Apply, Analyze, Evaluate, Create). (5=perfect alignment, 1=complete misalignment).

4. 'critique':
   - Provide a precise ONE-SENTENCE critique detailing specific pedagogical strengths or defects for each question.

5. 'overall_quality_score':
   - Provide the computed average of all individual scores across all questions and criteria (out of 5.0).

Questions to Audit:
{json.dumps(questions_dump, indent=2)}
"""

    contents = []
    if source_images and len(source_images) > 0:
        for img_bytes in source_images:
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        contents.append(
            types.Part.from_text(
                text=f"{judge_prompt}\n\n[Source Material: Please verify questions against the attached {len(source_images)} page image(s).]"
            )
        )
    else:
        text_content = (source_text or "")[:8000]
        contents.append(
            types.Part.from_text(
                text=f"{judge_prompt}\n\n### Source Material:\n{text_content}"
            )
        )

    response = _call_gemini_with_retry(
        client=client,
        model_name=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EvaluationReport,
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        ),
        backoffs=(1,),
    )

    raw_json = response.text or "{}"
    report = EvaluationReport.model_validate_json(raw_json)

    question_map = {q.id: q for q in questions}
    for ev in report.evaluations:
        orig_q = question_map.get(ev.question_id)
        if orig_q and orig_q.question_type == "Short Answer":
            ev.distractor_quality_score = 5

    if report.evaluations:
        fc_avg = sum(e.factual_correctness_score for e in report.evaluations) / len(report.evaluations)
        dq_avg = sum(e.distractor_quality_score for e in report.evaluations) / len(report.evaluations)
        ba_avg = sum(e.bloom_accuracy_score for e in report.evaluations) / len(report.evaluations)
        overall = (fc_avg + dq_avg + ba_avg) / 3.0

        report.factual_correctness_avg = round(fc_avg, 2)
        report.distractor_quality_avg = round(dq_avg, 2)
        report.bloom_accuracy_avg = round(ba_avg, 2)
        report.overall_quality_score = round(overall, 2)

    return report


# ==============================================================================
# AI Short-Answer Grading Function
# ==============================================================================

def grade_short_answers(
    api_key: str,
    submissions: List[dict],
    model_name: str = "gemini-3.8-flash",
) -> dict[int, ShortAnswerGrade]:
    """
    Grades submitted short-answer responses against model answers in one fast call.
    """
    if not submissions:
        return {}

    client = _create_client(api_key)
    prompt = f"""
You are a fair, strict academic grader. Grade each student's short-answer response against the model answer.
Rules:
- If the student response is blank, says "I don't know", "not sure", or is off-topic, strictly assign verdict="Incorrect" and score=0.0.
- Assign verdict="Correct" (score=1.0) only if key concepts from the model answer are accurately stated.
- Assign verdict="Partial" (score=0.5) if partially accurate but missing key details.
- Provide a single constructive sentence of feedback per question.

Submissions:
{json.dumps(submissions, indent=2)}
"""

    response = _call_gemini_with_retry(
        client=client,
        model_name=model_name,
        contents=[types.Part.from_text(text=prompt)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ShortAnswerBatchReport,
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        ),
        backoffs=(1,),
    )
    report = ShortAnswerBatchReport.model_validate_json(response.text or '{"grades": []}')
    return {g.question_id: g for g in report.grades}


# Alias for backwards compatibility
generate_questions = generate_assessment