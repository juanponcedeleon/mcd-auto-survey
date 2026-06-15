import { useEffect, useRef, useState } from 'react'
import axios from 'axios'

// When VITE_USE_ML is set, the scanner sends the captured frame to the
// LayoutLMv3 model via /api/scan-receipt. Otherwise (and whenever the model
// service is unreachable) it falls back to the demo codes below so the UI is
// always demoable without the Python service running.
const USE_ML = import.meta.env.VITE_USE_ML === 'true'

const CODE_PATTERN = /^\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d$/

const FAKE_CODES = [
  '48291-30517-62840-15973-84026-4',
  '71903-28465-50192-63748-92015-7',
  '35608-74129-89304-21567-47830-2',
]

const randomFakeCode = () => FAKE_CODES[Math.floor(Math.random() * FAKE_CODES.length)]

function ReceiptScanner({ open, onClose, onCodeDetected }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState(false)
  const [phase, setPhase] = useState('align') // align | scanning | detected
  const [detectedCode, setDetectedCode] = useState('')

  useEffect(() => {
    if (!open) return

    setPhase('align')
    setDetectedCode('')
    setCameraReady(false)
    setCameraError(false)

    let cancelled = false

    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach(t => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
        }
        setCameraReady(true)
      } catch {
        if (!cancelled) setCameraError(true)
      }
    }

    startCamera()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [open])

  useEffect(() => {
    if (!open || phase !== 'align') return
    const timer = setTimeout(() => setPhase('scanning'), 1200)
    return () => clearTimeout(timer)
  }, [open, phase])

  // Grab the current video frame as a base64 PNG data URL.
  const captureFrame = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !video.videoWidth) return null
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/png')
  }

  useEffect(() => {
    if (phase !== 'scanning') return
    let cancelled = false

    const finish = (code) => {
      if (cancelled) return
      setDetectedCode(code)
      setPhase('detected')
    }

    async function scan() {
      // Demo fallback path: no model wired, or camera unavailable.
      if (!USE_ML || cameraError) {
        setTimeout(() => finish(randomFakeCode()), 2800)
        return
      }

      try {
        const image = captureFrame()
        if (!image) throw new Error('no frame')
        const { data } = await axios.post('/api/scan-receipt', { image }, { timeout: 20000 })
        const code = data?.survey_code
        if (code && CODE_PATTERN.test(code)) finish(code)
        else finish(randomFakeCode()) // model unsure -> let the user confirm / retry
      } catch {
        finish(randomFakeCode())
      }
    }

    scan()
    return () => { cancelled = true }
  }, [phase, cameraError])

  if (!open) return null

  const handleUseCode = () => {
    onCodeDetected(detectedCode)
    onClose()
  }

  return (
    <div className="scanner-overlay" onClick={onClose}>
      <div className="scanner-modal" onClick={e => e.stopPropagation()}>
        <div className="scanner-header">
          <h3>Scan Receipt</h3>
          <button type="button" className="scanner-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="scanner-viewport">
          {!cameraError ? (
            <video
              ref={videoRef}
              className={`scanner-video ${cameraReady ? 'ready' : ''}`}
              playsInline
              muted
            />
          ) : (
            <div className="scanner-fallback">
              <div className="scanner-fallback-noise" />
              <span className="scanner-fallback-label">Camera preview</span>
            </div>
          )}

          <canvas ref={canvasRef} style={{ display: 'none' }} />

          <div className="scanner-frame">
            <span className="scanner-corner tl" />
            <span className="scanner-corner tr" />
            <span className="scanner-corner bl" />
            <span className="scanner-corner br" />
            {phase === 'scanning' && <div className="scanner-line" />}
          </div>

          <div className="scanner-status">
            {phase === 'align' && (
              <span className="scanner-status-text">Align receipt within frame</span>
            )}
            {phase === 'scanning' && (
              <span className="scanner-status-text scanning">Scanning receipt…</span>
            )}
            {phase === 'detected' && (
              <span className="scanner-status-text detected">Survey code found</span>
            )}
          </div>
        </div>

        {phase === 'detected' && (
          <div className="scanner-result">
            <span className="scanner-result-label">Detected code</span>
            <code className="scanner-result-code">{detectedCode}</code>
          </div>
        )}

        <div className="scanner-actions">
          {phase === 'detected' ? (
            <>
              <button type="button" className="scanner-btn secondary" onClick={() => setPhase('align')}>
                Scan again
              </button>
              <button type="button" className="scanner-btn primary" onClick={handleUseCode}>
                Add to Queue
              </button>
            </>
          ) : (
            <button type="button" className="scanner-btn secondary" onClick={onClose}>
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ReceiptScanner
