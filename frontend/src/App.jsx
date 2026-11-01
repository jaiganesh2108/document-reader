import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Upload, ChevronLeft, ChevronRight, Play, Pause, Square, Volume2, VolumeX,
  FileText, AlertCircle, X, MonitorPlay, Sparkles
} from 'lucide-react';
import './App.css';

const MAX_FILE_BYTES = 25 * 1024 * 1024;

const SAMPLE_SLIDES = [
  { slide_number: 1, content: "Introduction to Cloud Computing\n\nModule 1: Architectural Foundations\n- Infrastructure as a Service (IaaS)\n- Platform as a Service (PaaS) and Software as a Service (SaaS)\n- Shared responsibility security models", is_empty: false },
  { slide_number: 2, content: "Elasticity & Resource Scaling\n\nKey Principles:\n- Horizontal vs vertical scaling\n- Automatic load balancing across regions\n- Minimizing cold-start latency in serverless containers", is_empty: false },
  { slide_number: 3, content: "Data Persistence & Storage\n\nStorage Classes:\n- Block storage for low-latency database disks\n- Object storage for unstructured assets and media files\n- Managed database backups and disaster recovery", is_empty: false }
];

async function readError(response, fallback) {
  const data = await response.json().catch(() => ({}));
  return data.detail || fallback;
}

const splitSlide = (content = "") => {
  const [title = "", ...rest] = content.trim().split("\n");
  return { title, body: rest.join("\n").trim() };
};

function buildFallbackSegments(content = "", explanation = "") {
  if (!content) return [];
  const lines = content.trim().split("\n");
  const title = lines[0]?.trim() || "";
  const bodyLines = lines.slice(1);

  const items = [];
  if (title) {
    items.push({ type: "title", text: title, lineIndex: -1 });
  }
  bodyLines.forEach((l, idx) => {
    if (l.trim()) {
      items.push({ type: "body", text: l.trim(), lineIndex: idx });
    }
  });

  if (items.length === 0) return [];

  const sentences = (explanation || "").match(/[^.!?]+[.!?]+/g) || [explanation || ""];
  const cleaned = sentences.map((s) => s.trim()).filter(Boolean);
  const totalSentences = cleaned.length || 1;
  const totalItems = items.length;

  return items.map((item, i) => {
    const start = Math.floor((i * totalSentences) / totalItems);
    const end = Math.floor(((i + 1) * totalSentences) / totalItems);
    const slice = cleaned.slice(start, Math.max(start + 1, end));
    return {
      ...item,
      narration: slice.join(" ") || item.text
    };
  });
}

function alignSegmentToRenderedSlide(segment, content = "") {
  const rawLineIndex = segment.line_index ?? segment.lineIndex;
  if (segment.type !== "body" || !Number.isInteger(rawLineIndex)) {
    return { ...segment, lineIndex: rawLineIndex };
  }

  const rawBodyLines = content.trim().split("\n").slice(1);
  const leadingEmptyLines = rawBodyLines.findIndex((line) => line.trim());
  const offset = leadingEmptyLines < 0 ? 0 : leadingEmptyLines;
  return { ...segment, lineIndex: Math.max(0, rawLineIndex - offset) };
}

function ExplanationText({ explanation, segments, activeSegment, presentation = false }) {
  if (!segments || segments.length === 0) {
    return <p className={presentation ? undefined : "explanation-text"}>{explanation}</p>;
  }

  return (
    <p className={presentation ? undefined : "explanation-text"}>
      {segments.map((segment, index) => {
        const narration = segment.narration || segment.text || "";
        const isActive = activeSegment?.chunk_id === segment.chunk_id;
        return (
          <span key={segment.chunk_id || index}>
            {isActive ? <span className="stage-highlight">{narration}</span> : narration}
            {index < segments.length - 1 ? " " : ""}
          </span>
        );
      })}
    </p>
  );
}

// Text scales with the stage (cqw units); long slides step down so nothing is cut off.
const sizeClass = (n = 0) => (n < 180 ? "lg" : n < 380 ? "md" : n < 700 ? "sm" : n < 1100 ? "xs" : "xxs");

/* ---------- Reusable pieces ---------- */

function SlideStage({ slide, index, total, fill, activeHighlight }) {
  const { title, body } = splitSlide(slide?.content);
  const bodyLines = body ? body.split("\n") : [];
  const isTitleHighlighted = activeHighlight?.type === "title";

  return (
    <div className="stage-frame">
      <div className={`stage size-${sizeClass((slide?.content || "").length)}${fill ? " fill" : ""}`}>
        <div className="stage-slide">
          {title ? (
            <h2 className="stage-title">
              {isTitleHighlighted ? (
                <span className="stage-highlight">{title}</span>
              ) : (
                title
              )}
            </h2>
          ) : null}
          <pre className="stage-body">
            {bodyLines.length > 0 ? (
              bodyLines.map((line, idx) => {
                const isLineHighlighted =
                  activeHighlight?.type === "body" &&
                  activeHighlight?.lineIndex === idx;
                return (
                  <span key={idx}>
                    {isLineHighlighted ? (
                      <span className="stage-highlight">{line}</span>
                    ) : (
                      line
                    )}
                    {idx < bodyLines.length - 1 ? "\n" : ""}
                  </span>
                );
              })
            ) : title ? (
              ""
            ) : (
              "No text found on this slide."
            )}
          </pre>
        </div>
        <span className="stage-count">{index + 1} / {total}</span>
      </div>
    </div>
  );
}

function TransportControls({ t, compact }) {
  const { isPlaying, isBusy, isPaused, onPlay, onPause, onStop, onPrev, onNext, atStart, atEnd,
    volume, muted, onVolume, onMute, progress, hasExplanation } = t;
  const playLabel = isPaused ? "Resume" : hasExplanation ? "Play" : "Explain & play";
  return (
    <div className={`transport${compact ? " is-compact" : ""}`}>
      <div className="transport-row">
        <button className="btn-icon-round" onClick={onPrev} disabled={atStart || isBusy} aria-label="Previous slide" title="Previous (←)">
          <ChevronLeft size={20} />
        </button>
        {isPlaying ? (
          <button className="btn-main is-pause" onClick={onPause} aria-label="Pause" title="Pause (Space)">
            <Pause size={18} className="fill" /><span>Pause</span>
          </button>
        ) : (
          <button className="btn-main" onClick={onPlay} disabled={isBusy} title="Play (Space)">
            {isBusy ? <span className="spinner spinner-light" aria-hidden="true" /> : <Play size={18} className="fill" />}
            <span>{isBusy ? "Preparing…" : playLabel}</span>
          </button>
        )}
        <button className="btn-icon-round" onClick={onStop} disabled={isBusy || (!isPlaying && !isPaused)} aria-label="Stop" title="Stop (S)">
          <Square size={16} className="fill" />
        </button>
        <button className="btn-icon-round" onClick={onNext} disabled={atEnd || isBusy} aria-label="Next slide" title="Next (→)">
          <ChevronRight size={20} />
        </button>
        <div className="volume">
          <button className="btn-icon-plain" onClick={onMute} aria-label={muted ? "Unmute" : "Mute"}>
            {muted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <input type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume}
            onChange={(e) => onVolume(Number(e.target.value))} aria-label="Volume" />
        </div>
      </div>
      <div className="audio-progress" role="progressbar" aria-label="Narration progress"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress)}>
        <span style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

/* ---------- App ---------- */

export default function App() {
  const [fileId, setFileId] = useState(null);
  const [fileName, setFileName] = useState("");
  const [slides, setSlides] = useState([]);
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [explanations, setExplanations] = useState({});
  const [slideSegments, setSlideSegments] = useState({});
  const [activeHighlight, setActiveHighlight] = useState(null);

  const [isUploading, setIsUploading] = useState(false);
  const [isExplaining, setIsExplaining] = useState(false);
  const [isPreparingVoice, setIsPreparingVoice] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const [isPlaying, setIsPlaying] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);
  const [progress, setProgress] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);

  // Presentation mode
  const [presenting, setPresenting] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [barVisible, setBarVisible] = useState(true);
  const [barHidden, setBarHidden] = useState(false); // "clean" mode: bar never shown
  const hideTimer = useRef(null);

  const audioRef = useRef(null);
  const fileInputRef = useRef(null);
  const audioCache = useRef(new Map());
  const activeHighlightRef = useRef(null);
  const syncFrameRef = useRef(null);

  const currentSlide = slides[currentSlideIndex] || null;
  const totalSlides = slides.length;
  const currentExplanation = currentSlide ? explanations[currentSlide.slide_number] || "" : "";
  const currentSegments = currentSlide
    ? slideSegments[currentSlide.slide_number] ||
      buildFallbackSegments(currentSlide.content, currentExplanation)
    : [];
  const isBusy = isExplaining || isPreparingVoice;
  const isPaused = hasAudio && !isPlaying && progress > 0;
  const cacheKey = currentSlide ? `${fileId}:${currentSlide.slide_number}` : "";

  const stopAudioPlayback = useCallback(() => {
    const a = audioRef.current;
    if (a) { a.pause(); a.currentTime = 0; }
    if (syncFrameRef.current !== null) {
      cancelAnimationFrame(syncFrameRef.current);
      syncFrameRef.current = null;
    }
    setIsPlaying(false);
    setProgress(0);
    activeHighlightRef.current = null;
    setActiveHighlight(null);
  }, []);

  const clearAudioCache = useCallback(() => {
    audioCache.current.forEach(({ url }) => URL.revokeObjectURL(url));
    audioCache.current.clear();
    setHasAudio(false);
  }, []);

  // Slide change: stop and restore this slide's saved audio, if any
  useEffect(() => {
    stopAudioPlayback();
    setActiveHighlight(null);
    const entry = audioCache.current.get(cacheKey);
    const a = audioRef.current;
    if (entry && a) { a.src = entry.url; setHasAudio(true); }
    else { a?.removeAttribute("src"); setHasAudio(false); }
  }, [cacheKey, stopAudioPlayback]);

  useEffect(() => { if (audioRef.current) audioRef.current.volume = muted ? 0 : volume; }, [volume, muted]);

  useEffect(() => {
    const cache = audioCache.current;
    const audio = audioRef.current;
    return () => { audio?.pause(); cache.forEach(({ url }) => URL.revokeObjectURL(url)); cache.clear(); };
  }, []);

  const resetDocument = (id, name, newSlides) => {
    stopAudioPlayback(); clearAudioCache();
    setFileId(id); setFileName(name); setSlides(newSlides);
    setCurrentSlideIndex(0); setExplanations({});
    setSlideSegments({}); setActiveHighlight(null);
  };

  const handleUploadFile = async (file) => {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'pptx') { setErrorMessage("Please upload a PDF or PowerPoint (.pptx) file."); return; }
    if (file.size > MAX_FILE_BYTES) { setErrorMessage("This file is larger than 25 MB. Please upload a smaller one."); return; }
    setErrorMessage(""); setIsUploading(true); stopAudioPlayback();
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch("/api/upload", { method: "POST", body: formData });
      if (!response.ok) throw new Error(await readError(response, "Failed to process document."));
      const data = await response.json();
      resetDocument(data.file_id, data.filename, data.slides || []);
    } catch (err) {
      setErrorMessage(err.message || "An error occurred during file upload.");
    } finally { setIsUploading(false); }
  };

  const handleLoadSample = () => { setErrorMessage(""); resetDocument(null, "Cloud_Computing_Overview.pdf", SAMPLE_SLIDES); };

  const handleDrop = (e) => { e.preventDefault(); setIsDragging(false); if (!isUploading) handleUploadFile(e.dataTransfer.files?.[0]); };

  // Returns the explanation text for the current slide (fetching it if needed)
  const ensureExplanation = async () => {
    if (!currentSlide) return "";
    const slideNum = currentSlide.slide_number;
    if (explanations[slideNum]) return explanations[slideNum];
    setErrorMessage(""); setIsExplaining(true); stopAudioPlayback();
    try {
      const response = await fetch("/api/explain", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slide_number: slideNum, content: currentSlide.content, file_id: fileId })
      });
      if (!response.ok) throw new Error(await readError(response, "Failed to generate explanation."));
      const data = await response.json();
      setExplanations((prev) => ({ ...prev, [slideNum]: data.explanation }));
      if (data.segments && data.segments.length > 0) {
        const alignedSegments = data.segments.map((segment) =>
          alignSegmentToRenderedSlide(segment, currentSlide.content)
        );
        setSlideSegments((prev) => ({ ...prev, [slideNum]: alignedSegments }));
      }
      return data.explanation;
    } catch (err) {
      setErrorMessage(err.message || "Failed to generate the explanation.");
      return "";
    } finally { setIsExplaining(false); }
  };

  const playFrom = (a) => a.play().then(() => setIsPlaying(true)).catch((err) => { console.warn(err); setIsPlaying(false); });

  const speak = async (text) => {
    const a = audioRef.current;
    if (!text || !a) return;
    const key = cacheKey;
    setErrorMessage(""); setIsPreparingVoice(true);
    try {
      const response = await fetch("/api/speech", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, speed: 1.0 })
      });
      if (!response.ok) throw new Error(await readError(response, "Failed to synthesize teacher speech."));
      const url = URL.createObjectURL(await response.blob());
      audioCache.current.set(key, { url });
      if (key !== cacheKey) return; // slide changed while loading
      a.src = url; setHasAudio(true);
      await playFrom(a);
    } catch (err) {
      setErrorMessage(err.message || "Speech synthesis failed. Please try again.");
    } finally { setIsPreparingVoice(false); }
  };

  // One button: explain if needed, then speak, or resume saved audio
  const handlePlay = async () => {
    if (isBusy || !currentSlide) return;
    const a = audioRef.current;
    if (hasAudio && a) { playFrom(a); return; }
    await speak(await ensureExplanation());
  };
  const handlePause = () => audioRef.current?.pause();

  const goToSlide = useCallback((d) => setCurrentSlideIndex((i) => Math.min(Math.max(i + d, 0), Math.max(totalSlides - 1, 0))), [totalSlides]);

  /* ----- Presentation mode ----- */
  const enterPresentation = () => {
    if (!totalSlides) return;
    setPresenting(true); setBarVisible(true);
    document.documentElement.requestFullscreen?.().catch(() => {}); // falls back to in-window mode
  };
  const exitPresentation = useCallback(() => {
    setPresenting(false);
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  }, []);

  useEffect(() => {
    const onFs = () => { if (!document.fullscreenElement) setPresenting(false); };
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const revealBar = useCallback(() => {
    setBarVisible(true);
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setBarVisible(false), 3000);
  }, []);
  useEffect(() => { if (presenting) revealBar(); return () => clearTimeout(hideTimer.current); }, [presenting, revealBar]);

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "arrowright" && !isBusy) goToSlide(1);
      else if (k === "arrowleft" && !isBusy) goToSlide(-1);
      else if (k === " " && !e.target.closest?.("button")) { e.preventDefault(); isPlaying ? handlePause() : handlePlay(); }
      else if (k === "s") stopAudioPlayback();
      else if (k === "p" && !presenting) enterPresentation();
      else if (k === "escape" && presenting) exitPresentation();
      else if (k === "c" && presenting) { setBarHidden((h) => !h); setBarVisible(true); }
      else if (k === "t" && presenting) setCaptions((c) => !c);
      else if (k === "m") setMuted((m) => !m);
      if (presenting) revealBar();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const updateAudioProgress = useCallback((currentTime, duration) => {
    if (!duration || duration <= 0) {
      setProgress(0);
      return;
    }
    setProgress((currentTime / duration) * 100);

    const currentSlideNum = currentSlide?.slide_number;
    const segments =
      slideSegments[currentSlideNum] ||
      buildFallbackSegments(currentSlide?.content, currentExplanation);

    if (!segments || segments.length === 0) {
      setActiveHighlight(null);
      return;
    }

    const weights = segments.map((segment) => Math.max(
      1,
      segment.timing_weight || (segment.narration || segment.text || "").split(/\s+/).length
    ));
    const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
    if (totalWeight === 0) return;

    const currentTimeClamped = Math.min(Math.max(currentTime, 0), Math.max(duration - 0.001, 0));
    let accumulated = 0;
    let active = segments[0];

    for (let i = 0; i < segments.length; i++) {
      const segmentDuration = (weights[i] / totalWeight) * duration;
      if (currentTimeClamped < accumulated + segmentDuration) {
        active = segments[i];
        break;
      }
      accumulated += segmentDuration;
    }

    const previous = activeHighlightRef.current;
    const changed = !previous ||
      previous.chunk_id !== active.chunk_id ||
      previous.lineIndex !== active.lineIndex ||
      previous.type !== active.type;
    if (changed) {
      activeHighlightRef.current = active;
      setActiveHighlight(active);
    }
  }, [currentSlide, currentExplanation, slideSegments]);

  const activeExplanationSegment = isPlaying || activeHighlight
    ? currentSegments.find((segment) => segment.chunk_id === activeHighlight?.chunk_id)
    : null;

  const stopHighlightSync = useCallback(() => {
    if (syncFrameRef.current !== null) {
      cancelAnimationFrame(syncFrameRef.current);
      syncFrameRef.current = null;
    }
  }, []);

  const startHighlightSync = useCallback(() => {
    stopHighlightSync();
    const sync = () => {
      const audio = audioRef.current;
      if (!audio || audio.paused || audio.ended) {
        syncFrameRef.current = null;
        return;
      }
      updateAudioProgress(audio.currentTime, audio.duration);
      syncFrameRef.current = requestAnimationFrame(sync);
    };
    sync();
  }, [stopHighlightSync, updateAudioProgress]);

  const transport = {
    isPlaying, isPaused, isBusy, hasExplanation: !!currentExplanation, progress, volume, muted,
    onPlay: handlePlay, onPause: handlePause, onStop: stopAudioPlayback,
    onPrev: () => goToSlide(-1), onNext: () => goToSlide(1),
    atStart: currentSlideIndex === 0, atEnd: currentSlideIndex >= totalSlides - 1,
    onVolume: (v) => { setVolume(v); setMuted(false); }, onMute: () => setMuted((m) => !m)
  };

  const audioEl = (
    <audio ref={audioRef} preload="auto" style={{ display: 'none' }}
      onEnded={() => {
        stopHighlightSync();
        setIsPlaying(false);
        setProgress(0);
        activeHighlightRef.current = null;
        setActiveHighlight(null);
      }}
      onPause={() => { stopHighlightSync(); setIsPlaying(false); }}
      onPlay={() => {
        setIsPlaying(true);
        startHighlightSync();
      }}
      onLoadedMetadata={(e) => updateAudioProgress(e.currentTarget.currentTime, e.currentTarget.duration)}
      onSeeked={(e) => updateAudioProgress(e.currentTarget.currentTime, e.currentTarget.duration)}
      onTimeUpdate={(e) => {
        const { currentTime, duration } = e.currentTarget;
        updateAudioProgress(currentTime, duration);
      }} />
  );

  /* ----- Student / presentation view: slide and captions only ----- */
  if (presenting && currentSlide) {
    const controlsOn = barVisible && !barHidden;
    return (
      <>
      <div className="present" onMouseMove={revealBar} onClick={revealBar}>
        <SlideStage fill slide={currentSlide} index={currentSlideIndex} total={totalSlides} activeHighlight={activeHighlight} />
        <aside className="present-side" aria-label="Explanation">
          <div className="side-head">
            <span>Teacher’s explanation</span>
            <span className={`live-dot${isPlaying ? " on" : ""}`} aria-hidden="true" />
          </div>
          <div className="side-text" aria-live="polite" aria-busy={isBusy}>
            {isBusy ? (
              <p className="side-empty"><span className="spinner spinner-light" />{isExplaining ? "Preparing the explanation…" : "Preparing the voice…"}</p>
            ) : captions && currentExplanation ? (
              <ExplanationText
                explanation={currentExplanation}
                segments={currentSegments}
                activeSegment={activeExplanationSegment}
                presentation
              />
            ) : (
              <p className="side-empty">{captions ? "The teacher will explain this slide shortly." : "Captions are off."}</p>
            )}
          </div>
          {errorMessage && <div className="present-error" role="alert"><AlertCircle size={16} />{errorMessage}</div>}
          <div className={`side-controls${controlsOn ? " is-visible" : ""}`}>
            <TransportControls t={transport} compact />
            <div className="present-actions">
              <button className={`chip${captions ? " is-on" : ""}`} onClick={() => setCaptions((c) => !c)} aria-pressed={captions}>Captions (T)</button>
              <button className="chip" onClick={() => setBarHidden(true)}>Hide controls (C)</button>
              <button className="chip" onClick={exitPresentation}><X size={14} />Exit (Esc)</button>
            </div>
          </div>
        </aside>
      </div>
      {audioEl}
      </>
    );
  }

  /* ----- Teacher dashboard ----- */
  return (
    <>
    <div className="app-container">
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-icon"><Volume2 className="icon" /></div>
          <div>
            <h1 className="brand-title">AI Virtual Teacher</h1>
            <p className="brand-subtitle">Upload, preview, and teach your slides aloud.</p>
          </div>
        </div>
        {totalSlides > 0 && (
          <button className="btn-present" onClick={enterPresentation}>
            <MonitorPlay size={18} />Start presentation <kbd>P</kbd>
          </button>
        )}
      </header>

      {errorMessage && (
        <div className="alert-error" role="alert">
          <AlertCircle className="alert-icon" /><span>{errorMessage}</span>
          <button className="alert-close" onClick={() => setErrorMessage("")} aria-label="Dismiss error"><X size={14} /></button>
        </div>
      )}

      {totalSlides === 0 ? (
        <section className="card upload-card" aria-labelledby="upload-title">
          <div className="card-header">
            <h2 className="card-title" id="upload-title">Start with your lesson</h2>
            <span className="card-hint">PDF or PPTX, up to 25 MB</span>
          </div>
          <div className={`dropzone${isDragging ? " is-dragging" : ""}${isUploading ? " is-busy" : ""}`}
            onClick={() => !isUploading && fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}
            role="button" tabIndex={0} aria-busy={isUploading}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef.current?.click(); } }}>
            {isUploading ? <span className="spinner" aria-hidden="true" /> : <Upload className="upload-icon" />}
            <p className="upload-prompt">{isUploading ? "Reading your slides…" : isDragging ? "Drop to upload" : "Click or drag a PDF or PPTX here"}</p>
            <p className="upload-subtext">Slide text is extracted once, so moving between slides is instant.</p>
          </div>
          <div className="sample-action-row">
            <span>No file handy?</span>
            <button type="button" className="btn-sample" disabled={isUploading} onClick={handleLoadSample}>Try sample slides</button>
          </div>
        </section>
      ) : (
        <main className="workspace">
          <aside className="rail" aria-label="Slides">
            <div className="file-status-bar">
              <FileText className="file-icon" /><span className="file-name">{fileName}</span>
            </div>
            <ol className="rail-list">
              {slides.map((s, i) => (
                <li key={s.slide_number}>
                  <button className={`rail-item${i === currentSlideIndex ? " is-active" : ""}`}
                    onClick={() => !isBusy && setCurrentSlideIndex(i)} aria-current={i === currentSlideIndex ? "true" : undefined}>
                    <span className="rail-num">{i + 1}</span>
                    <span className="rail-title">{splitSlide(s.content).title || "Untitled slide"}</span>
                    {explanations[s.slide_number] && <Sparkles size={12} className="rail-done" aria-label="Explained" />}
                  </button>
                </li>
              ))}
            </ol>
            <button className="btn-link" onClick={() => fileInputRef.current?.click()}>Replace file</button>
          </aside>

          <section className="stage-column" aria-label="Slide preview">
            <SlideStage slide={currentSlide} index={currentSlideIndex} total={totalSlides} activeHighlight={activeHighlight} />
            <p className="preview-note">Preview shows the text extracted from each slide, not the original page layout.</p>

            <div className="card control-panel" aria-label="Teacher controls">
              <div className="card-header">
                <h2 className="card-title">Teacher controls</h2>
                <span className="slide-counter" aria-live="polite">Slide {currentSlideIndex + 1} of {totalSlides}</span>
              </div>
              <TransportControls t={transport} />
              <div className="explain-box" aria-live="polite" aria-busy={isExplaining}>
                {isExplaining ? <span className="loading-state"><span className="spinner" />Writing the explanation…</span>
                  : currentExplanation ? (
                    <ExplanationText
                      explanation={currentExplanation}
                      segments={currentSegments}
                      activeSegment={activeExplanationSegment}
                    />
                  )
                  : <p className="placeholder-text">Press <strong>Explain &amp; play</strong> and the teacher will explain this slide aloud.</p>}
              </div>
              <details className="howto">
                <summary>Sharing in Zoom or Google Meet</summary>
                <p>Click <strong>Start presentation</strong>, then share this browser tab (Meet: <em>“A tab”</em>) or window. Zoom: tick <strong>“Share sound”</strong> so students hear the voice. Students see only the slide and captions. Use the keyboard to teach: <kbd>←</kbd> <kbd>→</kbd> slides, <kbd>Space</kbd> play/pause, <kbd>S</kbd> stop, <kbd>T</kbd> captions, <kbd>C</kbd> hide controls, <kbd>Esc</kbd> exit. This app does not connect to Zoom or Meet itself.</p>
              </details>
            </div>
          </section>
        </main>
      )}

      <input type="file" ref={fileInputRef} accept=".pdf,.pptx" style={{ display: 'none' }}
        onChange={(e) => { handleUploadFile(e.target.files?.[0]); e.target.value = ""; }} />
    </div>
    {audioEl}
    </>
  );
}