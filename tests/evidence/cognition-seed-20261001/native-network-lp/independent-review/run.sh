#!/usr/bin/env bash
set -eu
cd /workspace/uniimente-kernel
PYTHONPATH=/workspace/uniimente-kernel /workspace/scratch/cortex-patched-venv/bin/python /workspace/scratch/p5-independent-certificate-review/qualify_certificates.py
