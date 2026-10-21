// Verifies UNIIMENTE Kernel inclusion proofs with Sigstore's shipped verifier.
// Usage:
//   npm pack @sigstore/verify@4.1.2 && tar xzf sigstore-verify-4.1.2.tgz
//   (cd package && npm install --omit=dev --ignore-scripts)
//   python scripts/dump_inclusion_proofs.py > proofs.json
//   node scripts/sigstore_inclusion_oracle.cjs $PWD/package/dist/tlog/merkle.js $PWD/proofs.json
const { verifyMerkleInclusion } = require(process.argv[2]);
const cases = require(process.argv[3]);
let ok = 0, bad = 0, tamperedRejected = 0;
for (const c of cases) {
  const entry = { canonicalizedBody: Buffer.from(c.leaf, 'utf8'),
    inclusionProof: { logIndex: String(c.index), hashes: c.hashes.map(h => Buffer.from(h, 'hex')) } };
  const checkpoint = { logSize: BigInt(c.n), logHash: Buffer.from(c.root, 'hex') };
  try { verifyMerkleInclusion(entry, checkpoint); ok++; } catch (e) { bad++; }
  const tampered = { ...entry, canonicalizedBody: Buffer.from(c.leaf.replace(/.$/, 'x'), 'utf8') };
  try { verifyMerkleInclusion(tampered, checkpoint); } catch (e) { tamperedRejected++; }
}
console.log(JSON.stringify({ cases: cases.length, accepted: ok, rejected: bad, tampered_rejected: tamperedRejected }));
