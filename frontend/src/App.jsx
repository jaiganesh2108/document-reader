import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, ChevronLeft, ChevronRight, Sparkles, Play, Pause, RotateCcw,
  Volume2, FileText, AlertCircle, Radio, CheckCircle2, X
} from 'lucide-react';
import './App.css';

const MAX_FILE_BYTES = 25 * 1024 * 1024;

const SAMPLE_SLIDES = [
  {
    slide_number: 1,
    content: "Course 1: Introduction to Cloud Computing\n\nModule 1: Architectural Foundations\n- Understanding Infrastructure as a Service (IaaS)\n- Platform as a Service (PaaS) and Software as a Service (SaaS)\n- Shared responsibility security models",
    is_empty: false
  },
  {
    slide_number: 2,
    content: "Elasticity & Resource Scaling\n\nKey Principles:\n- Horizontal scaling vs Vertical scaling\n- Automatic load balancing across regions\n- Minimizing cold-start latency in serverless containers",
    is_empty: false
  },
  {
    slide_number: 3,
    content: "Data Persistence & Storage\n\nStorage Classes:\n- Block storage for low-latency database disks\n- Object storage for unstructured assets and media files\n- Managed database backups and disaster recovery",
    is_empty: false
  }
];

async function readError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  return data.detail || fallback;
}

export default function App() {
  // Document state
  const [fileId, setFileId] = useState(null);
  const [fileName, setFileName] = useState("");
  const [slides, setSlides] = useState([]);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [explanations, setExplanations] = useState({}); // slide_number -> string

  // Status state
  const [isUploading, setIsUploading] = useState(false);
  const [isExplaining, setIsExplaining] = useState(false);
  const [isPreparingVoice, setIsPreparingVoice] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Audio state
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [audioProvider, setAudioProvider] = useState("");
  const [isAudioCached, setIsAudioCached] = useState(false);
  const [progress, setProgress] = useState(0);

  const audioRef = useRef(null);
  const fileInputRef = useRef(null);
  // `${fileId}:${slideNumber}` -> { url, provider, cached }
  const audioCache = useRef(new Map());

  const currentSlide = slides[currentSlideIndex] || null;
  const totalSlides = slides.length;
  const currentExplanation = currentSlide ? explanations[currentSlide.slide_number] || "" : "";
  const isBusy = isExplaining || isPreparingVoice;
  const cacheKey = currentSlide ? `${fileId}:${currentSlide.slide_number}` : "";

  const stopAudioPlayback = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setIsPlaying(false);
    setProgress(0);
  }, []);

  const clearAudioCache = useCallback(() => {
    audioCache.current.forEach(({ url }) => URL.revokeObjectURL(url));
    audioCache.current.clear();
    setHasAudio(false);
  }, []);

  // Slide change: stop audio and restore this slide's cached audio, if any
  useEffect(() => {
    stopAudioPlayback();
    const entry = audioCache.current.get(cacheKey);
    const audio = audioRef.current;
    if (entry && audio) {
      audio.src = entry.url;
      setHasAudio(true);
      setAudioProvider(entry.provider);
      setIsAudioCached(true);
    } else {
      if (audio) audio.removeAttribute("src");
      setHasAudio(false);
      setAudioProvider("");
      setIsAudioCached(false);
    }
  }, [cacheKey, stopAudioPlayback]);

  // Release audio and object URLs on unmount
  useEffect(() => {
    const cache = audioCache.current;
    return () => {
      audioRef.current?.pause();
      cache.forEach(({ url }) => URL.revokeObjectURL(url));
      cache.clear();
    };
  }, []);

  const resetDocument = (id, name, newSlides) => {
    stopAudioPlayback();
    clearAudioCache();
    setFileId(id);
    setFileName(name);
    setSlides(newSlides);
    setCurrentSlideIndex(0);
    setExplanations({});
  };

  const handleUploadFile = async (file) => {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'pptx') {
      setErrorMessage("Please upload a PDF or PowerPoint (.pptx) file.");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setErrorMessage("This file is larger than 25 MB. Please upload a smaller one.");
      return;
    }

    setErrorMessage("");
    setIsUploading(true);
    stopAudioPlayback();

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/upload", { method: "POST", body: formData });
      if (!response.ok) throw new Error(await readError(response, "Failed to process document."));
      const data = await response.json();
      resetDocument(data.file_id, data.filename, data.slides || []);
    } catch (err) {
      setErrorMessage(err.message || "An error occurred during file upload.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = () => {
    setErrorMessage("");
    resetDocument("sample-doc-01", "Cloud_Computing_Overview.pdf", SAMPLE_SLIDES);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (!isUploading) handleUploadFile(e.dataTransfer.files?.[0]);
  };

  const handleExplainSlide = async () => {
    if (!currentSlide || isBusy) return;
    const slideNum = currentSlide.slide_number;
    if (explanations[slideNum]) return;

    setErrorMessage("");
    setIsExplaining(true);
    stopAudioPlayback();

    try {
      const response = await fetch("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slide_number: slideNum, content: currentSlide.content, file_id: fileId })
      });
      if (!response.ok) throw new Error(await readError(response, "Failed to generate explanation."));
      const data = await response.json();
      setExplanations((prev) => ({ ...prev, [slideNum]: data.explanation }));
    } catch (err) {
      setErrorMessage(err.message || "Failed to generate the explanation.");
    } finally {
      setIsExplaining(false);
    }
  };

  const playFrom = (audio) =>
    audio.play().then(() => setIsPlaying(true)).catch((err) => {
      console.warn("Playback notice:", err);
      setIsPlaying(false);
    });

  const handlePlayExplanation = async () => {
    const audio = audioRef.current;
    if (!currentExplanation || isBusy || !audio) return;

    // Resume or replay audio already loaded for this slide
    if (hasAudio) {
      playFrom(audio);
      return;
    }

    setErrorMessage("");
    setIsPreparingVoice(true);
    const key = cacheKey;

    try {
      const response = await fetch("/api/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: currentExplanation, speed: 1.0 })
      });
      if (!response.ok) throw new Error(await readError(response, "Failed to synthesize teacher speech."));

      const provider = response.headers.get("x-tts-provider") || "AI teacher voice";
      const url = URL.createObjectURL(await response.blob());
      audioCache.current.set(key, { url, provider, cached: true });

      // The slide may have changed while the voice was loading
      if (key !== cacheKey) return;
      audio.src = url;
      setHasAudio(true);
      setAudioProvider(provider);
      setIsAudioCached(response.headers.get("x-audio-cached") === "true");
      await playFrom(audio);
    } catch (err) {
      setErrorMessage(err.message || "Speech synthesis failed. Please try again.");
    } finally {
      setIsPreparingVoice(false);
    }
  };

  const handlePauseAudio = () => audioRef.current?.pause();

  const handleReplayAudio = () => {
    const audio = audioRef.current;
    if (audio && hasAudio) {
      audio.currentTime = 0;
      playFrom(audio);
    }
  };

  const goToSlide = useCallback((delta) => {
    setCurrentSlideIndex((i) => Math.min(Math.max(i + delta, 0), Math.max(totalSlides - 1, 0)));
  }, [totalSlides]);

  // Arrow-key navigation (ignored while busy)
  useEffect(() => {
    const onKey = (e) => {
      if (isBusy || e.target.closest?.("input, textarea, button")) return;
      if (e.key === "ArrowRight") goToSlide(1);
      if (e.key === "ArrowLeft") goToSlide(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [goToSlide, isBusy]);

  const openPicker = () => !isUploading && fileInputRef.current?.click();

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon"><Volume2 className="icon" /></div>
          <div>
            <h1 className="brand-title">AI Virtual Teacher</h1>
            <p className="brand-subtitle">Upload your slides and hear each one explained, in a natural voice.</p>
          </div>
        </div>
        <span className="voice-tag">
          <span className="status-dot" aria-hidden="true"></span>
          Voice: Gemini TTS / Neerja Neural
        </span>
      </header>

      <div className="meeting-tip-banner">
        <Radio className="tip-icon" />
        <span>
          <strong>Teaching online?</strong> In Google Meet, share <em>“A tab”</em>. In Zoom, turn on <strong>“Share sound”</strong>. Students will then hear the narration.
        </span>
      </div>

      {errorMessage && (
        <div className="alert-error" role="alert">
          <AlertCircle className="alert-icon" />
          <span>{errorMessage}</span>
          <button className="alert-close" onClick={() => setErrorMessage("")} aria-label="Dismiss error">
            <X size={14} />
          </button>
        </div>
      )}

      <main className="main-content">
        <section className="card upload-card" aria-labelledby="upload-title">
          <div className="card-header">
            <h2 className="card-title" id="upload-title">Upload your slides</h2>
            <span className="card-hint">PDF or PPTX, up to 25 MB</span>
          </div>

          <div
            className={`dropzone${isDragging ? " is-dragging" : ""}${isUploading ? " is-busy" : ""}`}
            onClick={openPicker}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            aria-busy={isUploading}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.pptx"
              onChange={(e) => {
                handleUploadFile(e.target.files?.[0]);
                e.target.value = ""; // allow re-selecting the same file
              }}
              style={{ display: 'none' }}
            />
            {isUploading ? <span className="spinner" aria-hidden="true"></span> : <Upload className="upload-icon" />}
            <p className="upload-prompt">
              {isUploading ? "Reading your slides…" : isDragging ? "Drop to upload" : "Click or drag a PDF or PPTX here"}
            </p>
            <p className="upload-subtext">Each file is read once, so moving between slides is instant.</p>
          </div>

          {fileName ? (
            <div className="file-status-bar">
              <FileText className="file-icon" />
              <span className="file-name">{fileName}</span>
              <span className="file-badge">{totalSlides} {totalSlides === 1 ? "slide" : "slides"}</span>
            </div>
          ) : (
            <div className="sample-action-row">
              <span>No file handy?</span>
              <button type="button" className="btn-sample" disabled={isUploading} onClick={handleLoadSample}>
                Try sample slides
              </button>
            </div>
          )}
        </section>

        {totalSlides > 0 && (
          <section className="card slide-card" aria-labelledby="slide-title">
            <div className="card-header">
              <div className="slide-nav-meta">
                <h2 className="card-title" id="slide-title">Slide</h2>
                <span className="slide-counter" aria-live="polite">
                  {currentSlideIndex + 1} of {totalSlides}
                </span>
              </div>
              <div className="nav-controls">
                <button type="button" className="btn-nav" onClick={() => goToSlide(-1)}
                  disabled={currentSlideIndex === 0 || isBusy} aria-label="Previous slide">
                  <ChevronLeft className="btn-icon" /><span>Previous</span>
                </button>
                <button type="button" className="btn-nav" onClick={() => goToSlide(1)}
                  disabled={currentSlideIndex >= totalSlides - 1 || isBusy} aria-label="Next slide">
                  <span>Next</span><ChevronRight className="btn-icon" />
                </button>
              </div>
            </div>

            <div className="slide-progress" aria-hidden="true">
              <span style={{ width: `${((currentSlideIndex + 1) / totalSlides) * 100}%` }} />
            </div>

            <div className="slide-content-box" tabIndex={0} aria-label={`Text of slide ${currentSlideIndex + 1}`}>
              <pre className="slide-text">{currentSlide?.content || "No text found on this slide."}</pre>
            </div>

            <div className="action-row">
              <button type="button" className="btn-explain" onClick={handleExplainSlide}
                disabled={isBusy || !currentSlide || !!currentExplanation}>
                {isExplaining ? <span className="spinner spinner-light" aria-hidden="true"></span>
                  : currentExplanation ? <CheckCircle2 className="btn-icon" /> : <Sparkles className="btn-icon" />}
                {isExplaining ? "Writing explanation…" : currentExplanation ? "Explained" : "Explain this slide"}
              </button>
            </div>
          </section>
        )}

        {totalSlides > 0 && (
          <section className="card explanation-card" aria-labelledby="explain-title">
            <div className="card-header">
              <h2 className="card-title" id="explain-title">Teacher’s explanation</h2>
              {audioProvider && (
                <span className="provider-tag">Voice: {audioProvider}{isAudioCached ? " (saved)" : ""}</span>
              )}
            </div>

            <div className="explanation-box" aria-live="polite" aria-busy={isExplaining}>
              {isExplaining ? (
                <div className="loading-state">
                  <span className="spinner" aria-hidden="true"></span>
                  <p>Your teacher is preparing this slide…</p>
                </div>
              ) : currentExplanation ? (
                <p className="explanation-text">{currentExplanation}</p>
              ) : (
                <p className="placeholder-text">
                  Select <strong>Explain this slide</strong> to get a clear, classroom-style explanation.
                </p>
              )}
            </div>

            {currentExplanation && (
              <div className="audio-player-panel">
                <div className="audio-controls-row">
                  {!isPlaying ? (
                    <button type="button" className="btn-audio-primary" onClick={handlePlayExplanation}
                      disabled={isBusy}>
                      {isPreparingVoice ? <span className="spinner spinner-light" aria-hidden="true"></span>
                        : <Play className="btn-icon fill" />}
                      {isPreparingVoice ? "Preparing voice…" : "Play explanation"}
                    </button>
                  ) : (
                    <button type="button" className="btn-audio-pause" onClick={handlePauseAudio}>
                      <Pause className="btn-icon fill" />Pause
                    </button>
                  )}
                  <button type="button" className="btn-audio-secondary" onClick={handleReplayAudio}
                    disabled={isBusy || !hasAudio} aria-label="Replay from the start">
                    <RotateCcw className="btn-icon" /><span>Replay</span>
                  </button>
                  <div className="audio-progress" role="progressbar" aria-label="Playback progress"
                    aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)}>
                    <span style={{ width: `${progress}%` }} />
                  </div>
                </div>
              </div>
            )}

            {/* Always mounted so the ref stays stable across slides */}
            <audio
              ref={audioRef}
              preload="auto"
              onEnded={() => { setIsPlaying(false); setProgress(0); }}
              onPause={() => setIsPlaying(false)}
              onPlay={() => setIsPlaying(true)}
              onTimeUpdate={(e) => {
                const { currentTime, duration } = e.currentTarget;
                if (duration) setProgress((currentTime / duration) * 100);
              }}
              style={{ display: 'none' }}
            />
          </section>
        )}
      </main>

      <footer className="app-footer">
        <p>AI Virtual Teacher · Built for Google Meet and Zoom classes</p>
      </footer>
    </div>
  );
}