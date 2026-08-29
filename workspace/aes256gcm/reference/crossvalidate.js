// Independent cross-check of the Python reference against OpenSSL via Node.
// Emits deterministic cases on stdout as JSON; the Python side recomputes them.
const crypto = require('crypto');

function xorshift(seed) {           // deterministic, implementation-independent
  let s = seed >>> 0;
  return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s; };
}
const rnd = xorshift(0x5eed1234);
const bytes = n => Buffer.from(Array.from({length: n}, () => rnd() & 0xff));

const cases = [];
// Fixed structural cases: empty/partial/aligned, 96-bit and non-96-bit IVs, tag lengths.
const shapes = [
  [0, 0, 12, 16], [0, 16, 12, 16], [16, 0, 12, 16], [1, 1, 12, 16],
  [15, 15, 12, 16], [16, 16, 12, 16], [17, 20, 12, 16], [64, 32, 12, 16],
  [0, 0, 8, 16], [16, 16, 8, 16], [16, 16, 16, 16], [20, 13, 60, 16],
  [16, 16, 12, 12], [16, 16, 12, 8], [16, 16, 12, 4],
];
shapes.forEach(([pt, aad, iv, tag], i) => cases.push({
  id: `shape-${String(i).padStart(3, '0')}`,
  key: bytes(32).toString('hex'), iv: bytes(iv).toString('hex'),
  aad: bytes(aad).toString('hex'), pt: bytes(pt).toString('hex'), tag_bytes: tag,
}));
for (let i = 0; i < 200; i++) {
  const ptLen = rnd() % 96, aadLen = rnd() % 48;
  const ivLen = [12, 12, 12, 8, 16, 1, 60][rnd() % 7];
  const tagLen = [16, 16, 16, 15, 14, 13, 12, 8, 4][rnd() % 9];
  cases.push({
    id: `rand-${String(i).padStart(3, '0')}`,
    key: bytes(32).toString('hex'), iv: bytes(ivLen).toString('hex'),
    aad: bytes(aadLen).toString('hex'), pt: bytes(ptLen).toString('hex'), tag_bytes: tagLen,
  });
}

for (const c of cases) {
  const cipher = crypto.createCipheriv('aes-256-gcm', Buffer.from(c.key, 'hex'),
    Buffer.from(c.iv, 'hex'), { authTagLength: c.tag_bytes });
  cipher.setAAD(Buffer.from(c.aad, 'hex'));
  const ct = Buffer.concat([cipher.update(Buffer.from(c.pt, 'hex')), cipher.final()]);
  c.ct = ct.toString('hex');
  c.tag = cipher.getAuthTag().toString('hex');
}
process.stdout.write(JSON.stringify({
  generator: 'node crypto (OpenSSL) aes-256-gcm',
  node_version: process.version,
  openssl_version: process.versions.openssl,
  count: cases.length, cases,
}, null, 1));
