# AI Virtual Teacher — Natural Female Voice & Classroom Document Assistant

An AI-powered teaching assistant application that converts PDF and PowerPoint (`.pptx`) presentations into conversational, pedagogical classroom explanations delivered by a realistic female teacher voice. Designed for live online teaching, interactive lecture prep, and seamless screen sharing in Google Meet and Zoom.

---

## 🌟 Overview

Teachers often need to explain complex slide decks clearly, with relatable examples and natural speech pauses, rather than mechanically reading bullet points aloud. 

This full-stack application provides:
1. **Slide Document Ingestion**: Upload PDF or PowerPoint presentations (up to 25MB). Extracts text slide-by-slide and caches the document so re-navigation is instantaneous.
2. **Pedagogical AI Teacher Persona**: Explains concepts in conversational Indian English following an experienced educator's 7-step sequence (context, core idea, analogy, term clarification, transition, and short recap).
3. **Modular Natural Female Voice Synthesis**:
   - **Primary Option**: **Gemini TTS** (`gemini-2.0-flash` with warm female voice `Aoede` or `Kore`), formatted with instructional speaking-style instructions and standard WAV container packaging.
   - **Fallback Option**: **Edge TTS** (`en-IN-NeerjaNeural`), an expressive Indian English female neural voice with a calibrated slightly slower speaking rate (`-5%`) for clear instructional delivery. No API key required.
   - **Modular Extensibility**: Pluggable adapter architecture ready for ElevenLabs without modifying frontend code.
4. **Dual-Layer Caching**: Reuses cached explanations and audio blobs both on the client and server to eliminate redundant LLM and TTS requests.
5. **Meeting-Ready Audio Playback**: Direct browser `<audio>` playback optimized for Google Meet and Zoom tab/window screen sharing with audio.

---

## 🏗️ Project Architecture

```
Company/
├── README.md                     # Root project documentation (this file)
├── venv/                         # Python virtual environment (Python 3.11+)
│
├── document-reader/              # FastAPI Backend
│   ├── main.py                   # FastAPI server entry point and API endpoints
│   ├── explainer.py              # Female educator prompt & 7-step explanation generator
│   ├── tts_engine.py             # Modular TTS service (Gemini TTS, Edge TTS, ElevenLabs stub)
│   ├── text_cleaner.py           # Speech normalizer (markdown removal, Big-O, abbreviation expansion)
│   ├── pdf_reader.py             # PDF slide extraction (PyMuPDF)
│   ├── ppt_reader.py             # PPTX slide extraction (python-pptx)
│   ├── speech_engine.py          # Legacy pyttsx3 CLI engine (preserved)
│   ├── test_backend.py           # Core logic & modular unit test suite
│   ├── test_api_endpoints.py     # FastAPI endpoint and caching integration tests
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Backend environment template
│   └── documents/                # Sample test presentation documents
│       └── sample.pdf
│
└── frontend/                     # React Single-Page Application (Vite)
    ├── src/
    │   ├── App.jsx               # Main virtual teacher classroom interface
    │   ├── App.css               # Clean, accessible styling
    │   ├── index.css             # Base styles and theme variables
    │   └── main.jsx              # React DOM mounting
    ├── index.html
    ├── package.json
    └── vite.config.js            # Reverse proxy config (/api -> http://localhost:8000)
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**

---

### Step 1: Set Up & Start the Backend

1. Navigate to the backend directory:
   ```bash
   cd document-reader
   ```

2. Activate your virtual environment:
   ```bash
   # Windows (PowerShell)
   ..\venv\Scripts\Activate.ps1

   # Windows (cmd)
   ..\venv\Scripts\activate.bat

   # macOS / Linux
   source ../venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   # Windows
   copy .env.example .env

   # macOS / Linux
   cp .env.example .env
   ```

   *(Optional)* Add your Gemini API key in `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   DEFAULT_VOICE=en-IN-NeerjaNeural
   PORT=8000
   ```
   > **Note:** The application works completely without an API key! If `GEMINI_API_KEY` is not present, the system automatically uses its built-in pedagogical teacher explanation generator and synthesizes voice via Edge TTS (`en-IN-NeerjaNeural`).

5. Start the FastAPI server:
   ```bash
   python main.py --server
   ```
   The backend will be live at **`http://localhost:8000`**.

---

### Step 2: Set Up & Start the Frontend

In a new terminal window:

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Launch the Vite development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to:
   ```
   http://localhost:5173
   ```

---

## 📡 API Reference

| Method | Endpoint | Description | Request Body / Params |
|---|---|---|---|
| `GET` | `/api/health` | Health check & active TTS provider status | None |
| `POST` | `/api/upload` | Upload PDF or PPTX (max 25MB); extracts and caches slides | `multipart/form-data` with `file` |
| `POST` | `/api/explain` | Generates 7-step female teacher explanation for a slide | `{"slide_number": int, "content": str, "file_id": str?}` |
| `POST` | `/api/speech` | Converts text to natural female speech audio (MP3/WAV) | `{"text": str, "voice": str?, "speed": float?}` |

### Headers Returned by `/api/speech`:
- `X-TTS-Provider`: Active synthesis engine (e.g., `Gemini TTS (Aoede)`, `Edge TTS (en-IN-NeerjaNeural)`, or `Cache`)
- `X-Audio-Cached`: `true` if served from the in-memory cache; `false` on initial synthesis
- `Content-Type`: `audio/mpeg` (for Edge TTS MP3) or `audio/wav` (for Gemini TTS WAV)

---

## 🎙️ Meeting-Based Teaching Compatibility (Google Meet & Zoom)

The AI Virtual Teacher is built specifically to allow teachers to share lessons with students in online classrooms without robotic interruptions or audio sync issues:

### For Google Meet:
1. Join or start your Google Meet session.
2. In the bottom toolbar, click **Present now** $\rightarrow$ select **A tab**.
3. Choose the browser tab running the **AI Virtual Teacher** (`http://localhost:5173`).
4. Ensure the **"Share tab audio"** toggle is **Checked / Enabled**.
5. Click **Share**. When you click **"Play Explanation"**, your students will hear the female AI teacher explanation through Meet with optimal audio fidelity.

### For Zoom:
1. Start your Zoom meeting.
2. Click **Share Screen** in the meeting toolbar.
3. Select the browser window running the AI Virtual Teacher.
4. In the bottom-left corner of the window selection dialog, check **"Share sound"** (or **"Share computer sound"**).
5. Click **Share**.

---

## 🧪 Testing & Verification

Comprehensive test suites are included to verify functionality:

### 1. Backend Core Logic & Modular Unit Tests
```bash
cd document-reader
python test_backend.py
```
**Tests Covered:**
- PDF extraction from `sample.pdf`
- PPTX extraction & empty slide detection
- Text normalization, Markdown stripping, and Big-O notation (`O(1)`, `O(N)`)
- Sentence-boundary chunking without cutting mid-sentence
- Female educator 7-step explanation & fallback generation
- In-memory explanation caching
- PCM to RIFF/WAV packaging
- Edge TTS and Gemini TTS provider registry

### 2. FastAPI Endpoint Integration Tests
```bash
cd document-reader
python test_api_endpoints.py
```
**Tests Covered:**
- `/api/health` response and provider metadata
- File format validation (400 on unsupported files)
- 0-byte upload rejection
- File upload parsing and instant hash-based cache retrieval
- Explanation generation and empty slide validation
- Speech endpoint validation, cache hits, and headers

### 3. Frontend Production Build Check
```bash
cd frontend
npm run build
```
Builds the production bundle using Vite to verify clean bundling and JSX syntax.

---

## ⚙️ Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Optional | `None` | Google Gemini API key. Enables Gemini 2.0 Flash explanations & Gemini TTS |
| `GEMINI_TTS_MODEL` | Optional | `gemini-2.0-flash` | Gemini model name used for native audio synthesis |
| `DEFAULT_VOICE` | Optional | `en-IN-NeerjaNeural` | Default Edge TTS voice (Indian English female) |
| `ELEVENLABS_API_KEY` | Optional | `None` | Optional API key for future ElevenLabs modular expansion |
| `PORT` | Optional | `8000` | Port for the FastAPI server |

---

## 💡 Troubleshooting & FAQs

- **Q: Do I need to pay for an API key to use this app?**  
  **A:** No. If you don't supply a `GEMINI_API_KEY`, the application automatically uses the built-in pedagogical fallback explanation generator and synthesizes speech using the free Microsoft Edge Neural voice (`en-IN-NeerjaNeural`).
- **Q: Why does the audio play smoothly on replay without any delay?**  
  **A:** Dual-layer caching stores the audio blob in the browser's memory (`URL.createObjectURL`) and in the backend LRU cache (`X-Audio-Cached: true`).
- **Q: Does it work with PowerPoint presentations?**  
  **A:** Yes. Both `.pdf` and `.pptx` presentations are supported. Text is extracted from titles, text frames, shapes, and tables.
- **Q: What happens if a slide has only images and no text?**  
  **A:** The slide is marked as visual/empty, and the female teacher provides a natural observational note rather than crashing.

