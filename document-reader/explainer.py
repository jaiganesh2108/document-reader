import os
import hashlib
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# System prompt for female teacher persona
TEACHER_PROMPT = """You are a friendly, knowledgeable female teacher conducting an online class. Explain the supplied content naturally, as though speaking directly to students. Use clear Indian English, simple vocabulary, conversational sentences, and relatable examples. Maintain a warm, confident, engaging teaching style. Avoid robotic wording, excessive repetition, and unnecessary introductions. Explain the concept accurately and return only the spoken teaching narration.

Teaching guidelines for every slide:
1. Understand the extracted content thoroughly and identify the main concept.
2. Explain the concept using simple, natural language. Avoid reading bullet points word for word.
3. Provide a relatable, real-world example or analogy when helpful to make the idea click. Clearly distinguish explanations and illustrative examples from facts present in the document.
4. Explain any difficult or technical terminology in clear, everyday words.
5. Use smooth transitions between ideas so the lecture flows logically and engagingly.
6. Avoid unnecessarily long explanations; keep the narrative concise, accurate, and faithful to the source material.
7. End with a short, memorable one-sentence recap.

Strict narration rules:
- Return ONLY the spoken teaching narration that will be read aloud.
- Do NOT include any markdown symbols (like **, *, #, backticks, or bullet dashes).
- Do NOT include stage directions, bracketed actions, emotion markers, or speaker headers (e.g., no '[Teacher]:', no '(pauses)', no '*smiles*').
- Avoid repetitive introductory greetings like 'Welcome back class' on every single slide."""

# In-memory explanation cache: hash(content, slide_number) -> explanation
_explanation_cache: Dict[str, str] = {}


def _get_content_hash(content: str, slide_number: int) -> str:
    key = f"{slide_number}:{content.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def generate_fallback_explanation(content: str, slide_number: int) -> str:
    """
    Pedagogical fallback generator that crafts a natural female teacher explanation
    following the 7-step teaching sequence when an external LLM key is not configured
    or during API connection failure.
    """
    clean_content = content.strip()
    if not clean_content or "No readable text" in clean_content:
        return (
            f"On slide {slide_number}, we have a visual diagram without text. "
            f"Let us observe the visual structure carefully. Diagrams like this typically "
            f"illustrate the relationships between our key components before we dive into the details."
        )

    lines = [line.strip() for line in clean_content.split('\n') if line.strip()]
    first_line = lines[0] if lines else "this topic"
    topic = first_line.lstrip("* -•▪▫◦0123456789.):#").strip()

    explanation_parts = [
        f"In slide {slide_number}, we are looking at {topic}."
    ]

    bullet_points = [
        line.lstrip("* -•▪▫◦0123456789.):#").strip()
        for line in lines[1:5]
        if line.strip()
    ]

    if bullet_points:
        explanation_parts.append(
            f"The primary concept here is {bullet_points[0]}."
        )
        if len(bullet_points) > 1:
            explanation_parts.append(
                f"Notice also how {bullet_points[1]} works in tandem with this."
            )

    # Relatable real-world analogy
    explanation_parts.append(
        "To make this relatable, think of this like a well-organized team or a real-world system, "
        "where each component has a defined responsibility so the whole operation runs smoothly without bottlenecks."
    )

    if len(bullet_points) > 2:
        explanation_parts.append(
            f"An important detail to note from our material is that {bullet_points[2]}."
        )

    # Short recap
    explanation_parts.append(
        f"To recap, {topic} gives us the foundation we need to build dependable and efficient systems."
    )

    return " ".join(explanation_parts)


def explain_slide_content(content: str, slide_number: int = 1) -> str:
    """
    Generates a natural, engaging female educator explanation for the given slide text.
    Uses cached result if available to avoid duplicate Gemini API calls.
    """
    cache_key = _get_content_hash(content, slide_number)
    if cache_key in _explanation_cache:
        return _explanation_cache[cache_key]

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        explanation = generate_fallback_explanation(content, slide_number)
        _explanation_cache[cache_key] = explanation
        return explanation

    # Call Gemini using google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        user_prompt = (
            f"Slide Number: {slide_number}\n"
            f"Slide Extracted Content:\n{content}\n\n"
            f"Please deliver your natural spoken classroom explanation as the female teacher:"
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config={
                "system_instruction": TEACHER_PROMPT,
                "temperature": 0.7,
                "max_output_tokens": 650
            }
        )

        text = response.text.strip() if response and response.text else ""
        if text:
            # Clean quotation marks or accidental wrappers
            text = text.strip('"\'')
            _explanation_cache[cache_key] = text
            return text
        else:
            explanation = generate_fallback_explanation(content, slide_number)
            _explanation_cache[cache_key] = explanation
            return explanation

    except Exception as e:
        print(f"[Explainer] Gemini API notice ({e}). Using natural female educator fallback.")
        explanation = generate_fallback_explanation(content, slide_number)
        _explanation_cache[cache_key] = explanation
        return explanation
