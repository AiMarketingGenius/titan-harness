/**
 * Voice — Solon voice orb, full round-trip wired (Step 6.5).
 *
 * Press-and-hold → MediaRecorder captures audio → POST /api/titan/voice-in
 * (Whisper STT + LLM chat) → GET /api/titan/tts (ElevenLabs "alex" voice) →
 * play reply audio back.
 *
 * State machine:
 *   idle → listening (hold) → thinking (release; round-trip) → speaking (audio playing) → idle
 *   Any error state surfaces a toast; orb returns to idle after 2s.
 */
import { useRef, useState } from "react";

import { voiceApi, ServerError, NetworkError } from "../lib/api";


type OrbState = "idle" | "listening" | "thinking" | "speaking" | "error";


export function Voice() {
  const [state, setState] = useState<OrbState>("idle");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sessionIdRef = useRef<string>(`mobile-${Date.now()}`);

  async function startRecord() {
    setError(null);
    setTranscript(null);
    setReply(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        await handleAudio(blob);
      };
      rec.start();
      recorderRef.current = rec;
      setState("listening");
    } catch (exc) {
      const msg = (exc as Error).message || "";
      if (msg.includes("Permission denied") || msg.includes("NotAllowedError")) {
        setError("Microphone permission denied. Enable mic in browser settings.");
      } else if (msg.includes("NotFoundError")) {
        setError("No microphone found. Check device audio settings.");
      } else {
        setError(`Mic error: ${msg}`);
      }
      setState("error");
      setTimeout(() => setState("idle"), 2000);
    }
  }

  function stopRecord() {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }

  async function handleAudio(blob: Blob) {
    setState("thinking");
    try {
      const result = await voiceApi.voiceIn(blob, sessionIdRef.current);
      setTranscript(result.transcript || null);
      const replyText = result.reply || "";
      setReply(replyText);
      sessionIdRef.current = result.session_id || sessionIdRef.current;

      if (!replyText) {
        setState("idle");
        return;
      }

      // Fetch + play TTS
      setState("speaking");
      const audioBlob = await voiceApi.tts(replyText, "alex");
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        setState("idle");
      };
      audio.onerror = () => {
        URL.revokeObjectURL(audioUrl);
        setError("TTS playback failed.");
        setState("error");
        setTimeout(() => setState("idle"), 2000);
      };
      await audio.play();
    } catch (exc) {
      if (exc instanceof ServerError) {
        setError(`Server ${exc.status}: ${exc.detail ?? ""}`);
      } else if (exc instanceof NetworkError) {
        setError("Network error. Check connection.");
      } else {
        setError(`${(exc as Error).message || "voice pipeline error"}`);
      }
      setState("error");
      setTimeout(() => setState("idle"), 2000);
    }
  }

  return (
    <div className="page page-voice">
      <div className="voice-stage">
        <button
          type="button"
          className={`orb orb-${state}`}
          onPointerDown={startRecord}
          onPointerUp={stopRecord}
          onPointerCancel={stopRecord}
          onPointerLeave={stopRecord}
          aria-label={`Voice orb — ${state}`}
          aria-pressed={state === "listening"}
          disabled={state === "thinking" || state === "speaking"}
        >
          <span className="orb-pulse" aria-hidden="true" />
          <span className="orb-core" aria-hidden="true" />
        </button>
        <p className="orb-caption">
          {state === "idle" && "Hold to speak"}
          {state === "listening" && "Listening…"}
          {state === "thinking" && "Thinking…"}
          {state === "speaking" && "Speaking…"}
          {state === "error" && (error || "Error")}
        </p>

        {transcript && (
          <div className="transcript-card" aria-live="polite">
            <div className="transcript-label">You said</div>
            <div className="transcript-text">{transcript}</div>
          </div>
        )}

        {reply && (
          <div className="transcript-card reply-card" aria-live="polite">
            <div className="transcript-label">Titan</div>
            <div className="transcript-text">{reply}</div>
          </div>
        )}

        {error && state !== "error" && (
          <p className="toast toast-err" role="alert">{error}</p>
        )}
      </div>
    </div>
  );
}
