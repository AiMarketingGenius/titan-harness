/**
 * Voice — Solon voice orb.
 *
 * Step 6.4 scope: orb UI + press-to-talk gesture + audio capture via
 * MediaRecorder. Actual STT → LLM → TTS routing is wired in Step 6.5
 * (Deepgram + ElevenLabs via atlas_api /api/titan/{stt,tts,chat}).
 * For the scaffold, the orb captures audio + logs duration to verify
 * the gesture pipeline works end-to-end.
 */
import { useRef, useState } from "react";


type OrbState = "idle" | "listening" | "thinking" | "speaking" | "error";


export function Voice() {
  const [state, setState] = useState<OrbState>("idle");
  const [lastDurationMs, setLastDurationMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const startedAtRef = useRef<number>(0);

  async function startRecord() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      rec.onstop = () => {
        setLastDurationMs(Date.now() - startedAtRef.current);
        stream.getTracks().forEach((t) => t.stop());
        setState("thinking");
        // TODO Step 6.5: POST Blob to /api/titan/stt → /api/titan/chat → /api/titan/tts
        setTimeout(() => setState("idle"), 600);
      };
      rec.start();
      recorderRef.current = rec;
      startedAtRef.current = Date.now();
      setState("listening");
    } catch (exc) {
      setError(`mic error: ${(exc as Error).message}`);
      setState("error");
    }
  }

  function stopRecord() {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
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
        >
          <span className="orb-pulse" aria-hidden="true" />
          <span className="orb-core" aria-hidden="true" />
        </button>
        <p className="orb-caption">
          {state === "idle" && "Hold to speak"}
          {state === "listening" && "Listening…"}
          {state === "thinking" && "Thinking…"}
          {state === "speaking" && "Speaking…"}
          {state === "error" && "Mic permission needed"}
        </p>
        {lastDurationMs != null && (
          <p className="muted small">
            Last capture: {(lastDurationMs / 1000).toFixed(1)}s (STT wiring ships in Step 6.5)
          </p>
        )}
        {error && <p className="toast toast-err" role="alert">{error}</p>}
      </div>
    </div>
  );
}
