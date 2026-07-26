#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const vectorPath = path.join(root, "contracts", "ivio", "v1", "canonicalization-vectors.json");
const suite = JSON.parse(fs.readFileSync(vectorPath, "utf8"));

function canonicalize(value, cursor = "$") {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) {
      throw new Error(cursor + ": only safe integers are permitted");
    }
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map((item, index) => canonicalize(item, cursor + "[" + index + "]")).join(",") + "]";
  }
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    for (const key of keys) {
      if (!/^[\x20-\x7e]+$/.test(key)) {
        throw new Error(cursor + ": keys must be printable ASCII");
      }
    }
    return "{" + keys.map(
      (key) => JSON.stringify(key) + ":" + canonicalize(value[key], cursor + "." + key)
    ).join(",") + "}";
  }
  throw new Error(cursor + ": unsupported JSON value");
}

if (suite.profile !== "UNIIMENTE-C14N-v1") {
  throw new Error("unknown canonicalization profile");
}
for (const vector of suite.vectors) {
  const wire = canonicalize(vector.value);
  const digest = "sha256:" + crypto.createHash("sha256").update(wire, "utf8").digest("hex");
  if (wire !== vector.canonical_utf8) {
    throw new Error(vector.name + ": canonical bytes differ");
  }
  if (digest !== vector.sha256) {
    throw new Error(vector.name + ": digest differs");
  }
}

for (const invalid of suite.refusals) {
  try {
    canonicalize(invalid.value);
  } catch (error) {
    continue;
  }
  throw new Error(invalid.name + ": invalid canonical input was accepted");
}

console.log(
  "PASS IVIO v1 Node parity: " + suite.vectors.length +
  " canonical vectors, " + suite.refusals.length + " refusal vectors"
);
