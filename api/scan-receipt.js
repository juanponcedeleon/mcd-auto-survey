import axios from 'axios';

// Proxies a receipt image from the browser to the LayoutLMv3 inference service
// (ml/scripts/serve.py) and returns the extracted fields. Keeps the model URL
// server-side and shields the frontend from the Python service being down.
//
// Request:  POST { image: "data:image/png;base64,..." }
// Response: { survey_code, store_num, date, time, order_id, total, confidence }

export const config = { api: { bodyParser: { sizeLimit: '8mb' } } };

const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://localhost:8000/extract';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' });

  const { image } = req.body || {};
  if (!image) return res.status(400).json({ error: 'missing image' });

  try {
    // Strip the data-URL prefix and rebuild the raw bytes.
    const base64 = image.replace(/^data:image\/\w+;base64,/, '');
    const buffer = Buffer.from(base64, 'base64');

    const form = new FormData();
    form.append('file', new Blob([buffer], { type: 'image/png' }), 'receipt.png');

    const { data } = await axios.post(ML_SERVICE_URL, form, {
      headers: { Accept: 'application/json' },
      timeout: 20000,
      maxBodyLength: Infinity,
    });

    return res.status(200).json(data);
  } catch (err) {
    console.error('scan-receipt error', err?.response?.data ?? err.message);
    // Degrade gracefully so the frontend can fall back to manual entry.
    return res.status(502).json({ survey_code: null, error: 'ml-service-unavailable' });
  }
}
