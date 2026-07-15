import { useEffect, useRef, useState } from 'react'

const DEFAULT_BACKEND_URL = import.meta.env.VITE_RECEIPT_BACKEND_URL || 'http://127.0.0.1:8000'

function ReceiptScanner({ open, onClose, onCodeDetected, onReceiptParsed }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const previewCanvasRef = useRef(null)
  const [capturedFile, setCapturedFile] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState(false)
  const [phase, setPhase] = useState('capture') // capture | preview

  useEffect(() => {
    if (!open) return

    setPhase('capture')
    setCapturedFile(null)
    setSubmitError('')
    setIsSubmitting(false)
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

    if (navigator.mediaDevices?.getUserMedia) {
      startCamera()
    } else {
      setCameraError(true)
    }
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [open])

  if (!open) return null

  const handleClose = () => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    onClose()
  }

  const drawPreview = async (file) => {
    const previewCanvas = previewCanvasRef.current
    if (!previewCanvas) return
    const context = previewCanvas.getContext('2d')
    if (!context) return
    const bitmap = await createImageBitmap(file)
    const targetWidth = previewCanvas.clientWidth || 360
    const scale = targetWidth / bitmap.width
    previewCanvas.width = targetWidth
    previewCanvas.height = Math.max(1, Math.round(bitmap.height * scale))
    context.clearRect(0, 0, previewCanvas.width, previewCanvas.height)
    context.drawImage(bitmap, 0, 0, previewCanvas.width, previewCanvas.height)
  }

  const parseFile = async (file) => {
    setSubmitError('')
    setIsSubmitting(true)
    try {
      const formData = new FormData()
      formData.append('image', file, file.name || 'receipt.jpg')

      const response = await fetch(`${DEFAULT_BACKEND_URL}/parse-receipt`, {
        method: 'POST',
        body: formData,
      })

      let payload = null
      try {
        payload = await response.json()
      } catch {
        payload = null
      }

      if (!response.ok) {
        throw new Error(payload?.detail || payload?.error || 'Unable to parse receipt')
      }

      const surveyCode = payload?.fields?.survey_code?.value
      if (surveyCode) {
        onCodeDetected?.(surveyCode)
      }
      onReceiptParsed?.(payload)
      handleClose()
    } catch (error) {
      setSubmitError(error.message || 'Unable to parse receipt')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleCapture = async () => {
    const videoElement = videoRef.current
    if (!videoElement) return
    const canvas = document.createElement('canvas')
    canvas.width = videoElement.videoWidth || 1280
    canvas.height = videoElement.videoHeight || 720
    const context = canvas.getContext('2d')
    if (!context) {
      setSubmitError('Failed to capture camera frame')
      return
    }
    context.drawImage(videoElement, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92))
    if (!blob) {
      setSubmitError('Could not capture receipt image')
      return
    }
    const file = new File([blob], `receipt-${Date.now()}.jpg`, { type: 'image/jpeg' })
    setCapturedFile(file)
    await drawPreview(file)
    setPhase('preview')
  }

  const handleFileSelected = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setSubmitError('Please select an image file.')
      return
    }
    setSubmitError('')
    setCapturedFile(file)
    drawPreview(file)
      .then(() => setPhase('preview'))
      .catch(() => setSubmitError('Could not preview selected image.'))
  }

  const resetCapture = () => {
    setCapturedFile(null)
    setSubmitError('')
    setPhase('capture')
  }

  return (
    <div className="scanner-overlay" onClick={handleClose}>
      <div className="scanner-modal" onClick={e => e.stopPropagation()}>
        <div className="scanner-header">
          <h3>Parse Receipt</h3>
          <button type="button" className="scanner-close" onClick={handleClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="scanner-viewport">
          {!cameraError && phase === 'capture' ? (
            <video
              ref={videoRef}
              className={`scanner-video ${cameraReady ? 'ready' : ''}`}
              playsInline
              muted
            />
          ) : phase === 'preview' ? (
            <canvas ref={previewCanvasRef} className="scanner-preview-image" aria-label="Receipt preview image" />
          ) : (
            <div className="scanner-fallback">
              <span className="scanner-fallback-label">Camera unavailable. Upload a receipt image instead.</span>
            </div>
          )}

          {phase === 'capture' && !cameraError && (
            <div className="scanner-frame">
              <span className="scanner-corner tl" />
              <span className="scanner-corner tr" />
              <span className="scanner-corner bl" />
              <span className="scanner-corner br" />
            </div>
          )}

          <div className="scanner-status">
            {phase === 'capture' && (
              <span className="scanner-status-text">Align your receipt, then capture the image.</span>
            )}
            {phase === 'preview' && (
              <span className="scanner-status-text detected">Image ready to parse</span>
            )}
          </div>
        </div>

        <div className="scanner-upload-row">
          <label htmlFor="receipt-file" className="scanner-upload-label">Upload from file</label>
          <input id="receipt-file" type="file" accept="image/*" onChange={handleFileSelected} />
        </div>

        {submitError && <div className="error-message scanner-error">{submitError}</div>}

        <div className="scanner-actions">
          {phase === 'preview' ? (
            <>
              <button type="button" className="scanner-btn secondary" onClick={resetCapture} disabled={isSubmitting}>
                Retake
              </button>
              <button
                type="button"
                className="scanner-btn primary"
                onClick={() => capturedFile && parseFile(capturedFile)}
                disabled={!capturedFile || isSubmitting}
              >
                {isSubmitting ? 'Parsing…' : 'Parse Receipt'}
              </button>
            </>
          ) : (
            <>
              {!cameraError && (
                <button type="button" className="scanner-btn primary" onClick={handleCapture} disabled={!cameraReady}>
                  Capture
                </button>
              )}
              <button type="button" className="scanner-btn secondary" onClick={handleClose}>
                Cancel
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ReceiptScanner
