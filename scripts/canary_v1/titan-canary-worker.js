addEventListener('fetch', event => {
  event.respondWith(handle(event));
});

const NTFY = 'https://ntfy.sh/amg-sec-e5e9b77d';

async function handle(event) {
  const req = event.request;
  const url = new URL(req.url);
  const m = url.pathname.match(/^\/b\/([a-zA-Z0-9._-]+)$/);
  if (!m) {
    return new Response('Not Found', { status: 404, headers: { 'Cache-Control': 'no-store' } });
  }
  const tokenId = m[1];
  const extMatch = tokenId.match(/\.([a-z]+)$/i);
  const ext = extMatch ? extMatch[1].toLowerCase() : '';
  const ip = req.headers.get('cf-connecting-ip') || 'unknown';
  const ua = req.headers.get('user-agent') || 'unknown';
  const ref = req.headers.get('referer') || 'direct';
  const cc = (req.cf && req.cf.country) || 'unknown';
  const asn = (req.cf && req.cf.asn) || 'unknown';
  const ts = new Date().toISOString();
  const body = [
    '🚨 CANARY HIT',
    'token: ' + tokenId,
    'ip: ' + ip,
    'country: ' + cc,
    'asn: ' + asn,
    'ua: ' + ua,
    'ref: ' + ref,
    'ts: ' + ts,
  ].join('\n');

  event.waitUntil(
    fetch(NTFY, {
      method: 'POST',
      headers: {
        'Title': 'Canary hit: ' + tokenId,
        'Priority': 'urgent',
        'Tags': 'rotating_light,warning',
      },
      body: body,
    }).catch(() => {})
  );

  if (/^(png|gif|jpg|jpeg|webp|ico)$/.test(ext)) {
    const pngHex = '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6300010000050001a0a0a0350000000049454e44ae426082';
    const bytes = new Uint8Array(pngHex.match(/../g).map(h => parseInt(h, 16)));
    return new Response(bytes, { headers: { 'Content-Type': 'image/png', 'Cache-Control': 'no-store' } });
  }
  if (ext === 'pdf') {
    return new Response('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF', {
      headers: { 'Content-Type': 'application/pdf', 'Cache-Control': 'no-store' },
    });
  }
  return new Response('OK', { headers: { 'Content-Type': 'text/plain', 'Cache-Control': 'no-store' } });
}
