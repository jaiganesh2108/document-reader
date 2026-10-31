# AI Virtual Teacher — React Frontend

Clean, single-page React application for the **AI Virtual Teacher**, built with Vite and Tailwind/Vanilla CSS.

---

## Features

- **Document Dropzone**: Drag-and-drop or file picker supporting PDF and PowerPoint (`.pptx`) presentations (up to 25MB).
- **Slide Viewer & Navigator**: Clean slide content preview with Previous/Next controls and slide counter.
- **Explain Slide Action**: Generates conversational 7-step pedagogical female teacher explanations.
- **Female Voice Audio Player**:
  - Play, Pause, and Replay controls.
  - Shows active synthesis provider (Gemini TTS `Aoede` or Edge TTS `en-IN-NeerjaNeural`).
  - Client-side blob caching for instant replays without network overhead.
  - Automatically stops/pauses audio when navigating between slides.
- **Meeting-Ready Guidance**: Displays quick tips on enabling tab/sound sharing in Google Meet and Zoom.

---

## Development & Build

### Install dependencies:
```bash
npm install
```

### Run local dev server (port 5173):
```bash
npm run dev
```

### Build production bundle:
```bash
npm run build
```

### Preview production build:
```bash
npm run preview
```

---

## API Proxy Configuration

The development server proxies `/api` requests to the FastAPI backend running on port 8000 (configured in `vite.config.js`). Ensure the backend server is running before testing API operations.
