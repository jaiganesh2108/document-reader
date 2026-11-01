# AI Teaching Assistant — Natural Female Voice & Performance Upgrade

A FastAPI and React-powered virtual teaching assistant that extracts slide content from PDF and PowerPoint (`.pptx`) presentations, generates conversational classroom explanations with a natural female teacher persona, and synthesizes clear, pedagogical speech using a modular TTS architecture (Primary: **Gemini TTS** with natural female voice; Fallback: **Edge TTS `en-IN-NeerjaNeural`** with Indian English pronunciation).

---

## 1. Key Features

- **Document Extraction (Lightweight & Cached)**
  - Slide-by-slide text extraction for both **PDF** (via PyMuPDF) and **PowerPoint (.pptx)** (via python-pptx).
  - Handles empty pages or visual diagram slides gracefully without crashing.
  - Computes SHA-256 hash per file: documents are parsed **only once per upload** and cached in memory.

- **Pedagogical Female Teacher Explanations**
  - Prompted as an experienced, warm female educator conducting an online class in clear Indian English.
  - Follows a 7-step pedagogical structure: understanding content, identifying core concepts, conversational explanation, relatable real-world analogy, clarifying technical terms, smooth transitions, and a short memorable recap.
  - Built-in pedagogical fallback generator ensures offline or keyless operation produces natural classroom explanations.
  - Explanations are cached per slide to prevent duplicate Gemini API calls.

- **Modular Text-to-Speech (TTS) Architecture**
  - **Primary**: **Gemini TTS** with a prebuilt female voice (`Aoede` or `Kore`). Applies pedagogical speaking-style guidance for natural pauses and conversational cadence. Automatically wraps raw PCM into standard RIFF/WAV format.
  - **Fallback**: **Edge TTS (`en-IN-NeerjaNeural`)** — Free, expressive Indian English female neural voice with a calibrated slower speaking rate (-5%) for instructional clarity.
  - **Extensible**: Pluggable adapter architecture ready for ElevenLabs or custom neural voices without changing frontend code.
  - **In-Memory Audio Caching**: LRU-bounded cache reuses identical audio without repeated synthesis.

- **Meeting-Based Teaching Compatibility (Google Meet & Zoom)**
  - Audio plays directly through the browser tab via standard HTML5 `<audio>`.
  - Manual slide navigation with full Play / Pause / Replay controls.
  - Automatically pauses and resets previous audio when navigating between slides.

---

## 2. Project Architecture

```
Company/
├── document-reader/              # FastAPI Backend
│   ├── main.py                   # FastAPI server & endpoints (/api/upload, /api/explain, /api/speech)
│   ├── explainer.py              # Female educator prompt & 7-step explanation generator
│   ├── tts_engine.py             # Modular TTS service (Gemini TTS, Edge TTS fallback, ElevenLabs stub)
│   ├── text_cleaner.py           # Speech normalizer (removes markdown, formats Big-O, expands abbreviations)
│   ├── pdf_reader.py             # PDF slide extraction
│   ├── ppt_reader.py             # PPTX slide extraction
│   ├── speech_engine.py          # Legacy pyttsx3 CLI engine (preserved)
│   ├── test_backend.py           # Core logic & modular unit test suite
│   ├── test_api_endpoints.py     # FastAPI endpoint and caching integration tests
│   ├── requirements.txt
│   ├── .env.example
│   └── documents/                # Sample presentation documents
│
└── frontend/                     # Single-Page React Application (Vite)
    ├── src/
    │   ├── App.jsx               # Single-page classroom assistant interface
    │   ├── App.css               # Clean, accessible styling
    │   └── main.jsx
    ├── package.json
    └── vite.config.js            # API reverse proxy configuration (/api -> http://localhost:8000)
```

---

## 3. Installation & Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**

### Step 1: Set up the Backend

```bash
# Navigate to the backend directory
cd document-reader

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # On Windows
# source venv/bin/activate       # On macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env           # On Windows
# cp .env.example .env           # On macOS/Linux
```

Configure your `.env` file:

```env
# Optional: Google Gemini API key for AI explanations & Gemini TTS
# Get your free key at: https://aistudio.google.com/
GEMINI_API_KEY=your_key_here

# Gemini model for grounded explanations
GEMINI_MODEL=gemini-3.8-flash

# Default fallback voice (Edge TTS Indian English Female)
DEFAULT_VOICE=en-IN-NeerjaNeural

# Server Port
PORT=8000
```

> **Note:** The backend operates fully even without `GEMINI_API_KEY`. When no key is configured, it uses the built-in pedagogical teacher explanation generator and synthesizes voice via Edge TTS (`en-IN-NeerjaNeural`).

### Step 2: Set up the Frontend

```bash
# In a separate terminal, navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Build or start the development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 4. Running the Servers

### Run Backend Server:
```bash
cd document-reader
python main.py --server
```
Backend API will start at `http://localhost:8000`.

### Run Frontend:
```bash
cd frontend
npm run dev
```
Frontend UI will start at `http://localhost:5173`.

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Returns server health, Gemini configuration status, active voices, and cache stats |
| `POST` | `/api/upload` | Upload PDF or PPTX file (max 25MB). Extracts slides and caches them |
| `POST` | `/api/explain` | Generates a 7-step female teacher explanation for a slide. Caches by slide content |
| `POST` | `/api/speech` | Converts explanation text into natural female teacher speech (MP3/WAV) |

---

## 6. Google Meet & Zoom Screen Sharing Instructions

When presenting in an online class, follow these steps so students can hear the AI teacher's explanation:

### Google Meet:
1. Click **Present now** at the bottom of the Meet window.
2. Select **A tab** (preferred for best audio quality) and choose the `AI Virtual Teacher` tab.
3. Ensure the checkbox **Share tab audio** is enabled.
4. Click **Share**. When you click **Play Explanation**, audio will route directly to your students.

### Zoom:
1. Click **Share Screen** in the meeting toolbar.
2. Select the browser window running the application.
3. Check **Share sound** (or **Share computer sound**) in the bottom-left corner of the share window.
4. Click **Share**.

---

## 7. Running Tests

```bash
cd document-reader

# Run comprehensive core logic and modular tests:
python test_backend.py

# Run FastAPI endpoint and caching integration tests:
python test_api_endpoints.py
```

---

## 8. Limitations & API Costs

- **Gemini Free Tier**: Gemini 2.0 Flash is available with a generous free tier on Google AI Studio. Note that audio response modality availability can vary by key tier and quota. When Gemini audio modality is unavailable or rate-limited, the system automatically and silently falls back to Edge TTS.
- **Edge TTS**: Completely free, requiring no API key or subscription. Requires outbound HTTPS access to Microsoft speech endpoints.
- **In-Memory Caching**: Extracted slides, generated explanations, and synthesized audio blobs are held in memory during the server lifecycle without requiring external database or Redis infrastructure.
