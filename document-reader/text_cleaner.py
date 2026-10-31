import re
from typing import List


def split_text_into_chunks(text: str, max_chars: int = 1200) -> List[str]:
    """
    Splits text into chunks of at most `max_chars` along sentence boundaries.
    Never splits in the middle of a sentence.
    """
    if not text or len(text) <= max_chars:
        return [text] if text else []

    # Split on sentence boundaries: period, question mark, or exclamation mark followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_len = len(sentence)
        if current_length + sentence_len + 1 > max_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_length = sentence_len
        else:
            current_chunk.append(sentence)
            current_length += sentence_len + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def clean_text_for_speech(text: str) -> str:
    """
    Normalizes written educational explanations into natural, flowing spoken English.
    Removes Markdown characters, expands bullet points into spoken transitional sentences,
    preserves technical terminology, and formats punctuation to encourage natural breath
    pauses during TTS synthesis.
    """
    if not text or not text.strip():
        return ""

    cleaned = text.strip()

    # 1. Strip code blocks and inline code
    cleaned = re.sub(r'```[\w]*\n([\s\S]*?)```', r'Let us review the code example: \1', cleaned)
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)

    # 2. Strip Markdown headers (# Header)
    cleaned = re.sub(r'#+\s*', '', cleaned)

    # 3. Strip bold, italics, strikethrough, blockquotes (avoid matching bullet points across lines)
    cleaned = re.sub(r'\*\*([^\n*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'(?<!^)(?<!\n)\*([^\n*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^\n_]+)__', r'\1', cleaned)
    cleaned = re.sub(r'(?<!^)(?<!\n)_([^\n_]+)_', r'\1', cleaned)
    cleaned = re.sub(r'~~([^~]+)~~', r'\1', cleaned)
    cleaned = re.sub(r'^>\s+', '', cleaned, flags=re.MULTILINE)

    # 4. Remove Markdown links [text](url) -> text
    cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', cleaned)

    # 5. Remove divider lines and visual rules
    cleaned = re.sub(r'[-=_\*]{3,}', '', cleaned)

    # 6. Preserve and expand Big-O algorithmic notation before punctuation changes
    cleaned = re.sub(r'\bO\(1\)\s*(constant\s*time)?', 'O of 1 constant time ', cleaned)
    cleaned = re.sub(r'\bO\([nN]\)\s*(linear\s*time)?', 'O of N linear time ', cleaned)
    cleaned = re.sub(r'\bO\([nN]\s*log\s*[nN]\)', 'O of N log N time', cleaned)
    cleaned = re.sub(r'\bO\(log\s*[nN]\)', 'O of log N time', cleaned)
    cleaned = re.sub(r'\bO\([nN]\^2\)', 'O of N squared time', cleaned)

    # 7. Convert bullet points and numbered lists into flowing spoken language
    lines = cleaned.split('\n')
    processed_lines = []
    bullet_counter = 0

    transitions = [
        "First,",
        "Next,",
        "In addition,",
        "Furthermore,",
        "Another key point is,",
        "Finally,"
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for bullet point: *, -, +, •, ▪, ▫, ◦, ‣
        bullet_match = re.match(r'^[\*\-\+•▪▫◦‣\u2022\u2023\u25b6]\s+(.*)', stripped)
        num_match = re.match(r'^\d+[\.\)]\s+(.*)', stripped)

        if bullet_match or num_match:
            content = (bullet_match.group(1) if bullet_match else num_match.group(1)).strip()
            # If line doesn't end with punctuation, add a period
            if content and content[-1] not in '.!?:;':
                content += '.'

            # Use conversational transition prefix
            transition = transitions[bullet_counter % len(transitions)]
            bullet_counter += 1
            processed_lines.append(f"{transition} {content}")
        else:
            bullet_counter = 0
            if stripped[-1] not in '.!?:;':
                stripped += '.'
            processed_lines.append(stripped)

    spoken_text = " ".join(processed_lines)

    # 8. Normalize common abbreviations and Latin shorthand for natural pronunciation
    spoken_text = re.sub(r'\b[eE]\.[gG]\.\s*,?', 'for example, ', spoken_text)
    spoken_text = re.sub(r'\b[iI]\.[eE]\.\s*,?', 'that is, ', spoken_text)
    spoken_text = re.sub(r'\b[vV][sS]\.\s*', 'versus ', spoken_text)
    spoken_text = re.sub(r'\b[vV][sS]\b', 'versus', spoken_text)
    spoken_text = re.sub(r'\betc\.\s*', 'and so on. ', spoken_text)
    spoken_text = re.sub(r'\betc\b', 'and so on', spoken_text)
    spoken_text = re.sub(r'\bw\/\s*', 'with ', spoken_text)
    spoken_text = re.sub(r'\bw\/o\s*', 'without ', spoken_text)
    spoken_text = re.sub(r'\bapprox\.\s*', 'approximately ', spoken_text)
    spoken_text = re.sub(r'\bdept\.\s*', 'department ', spoken_text)
    spoken_text = re.sub(r'\bmin\.\s*', 'minimum ', spoken_text)
    spoken_text = re.sub(r'\bmax\.\s*', 'maximum ', spoken_text)
    spoken_text = re.sub(r'\b[nN]o\.\s*(\d+)', r'number \1', spoken_text)
    spoken_text = re.sub(r'\b[fF]ig\.\s*(\d+)', r'figure \1', spoken_text)

    # 9. Handle mathematical symbols and punctuation
    spoken_text = re.sub(r'%', ' percent', spoken_text)
    spoken_text = re.sub(r'\&', ' and ', spoken_text)
    spoken_text = re.sub(r'(\w+)\/(\w+)', r'\1 or \2', spoken_text)
    spoken_text = re.sub(r'\s*\+\s*', ' plus ', spoken_text)
    spoken_text = re.sub(r'\s*=\s*', ' equals ', spoken_text)

    # 10. Clean up quotes, brackets, and parentheticals without dropping inner content
    spoken_text = re.sub(r'["“”]', '', spoken_text)
    spoken_text = re.sub(r'[\[\]\(\)\{\}]', ' ', spoken_text)

    # 11. Normalize dashes and mid-sentence colons/semicolons into natural pauses
    spoken_text = re.sub(r'\s*[—–]\s*', ', ', spoken_text)
    spoken_text = re.sub(r'\s*:\s*', ', ', spoken_text)
    spoken_text = re.sub(r'\s*;\s*', '. ', spoken_text)

    # 12. Normalize multiple punctuation and whitespaces
    spoken_text = re.sub(r'\s+', ' ', spoken_text)
    spoken_text = re.sub(r'\s+([,\.!?:])', r'\1', spoken_text)
    spoken_text = re.sub(r'([,\.!?:])\1+', r'\1', spoken_text)

    return spoken_text.strip()
