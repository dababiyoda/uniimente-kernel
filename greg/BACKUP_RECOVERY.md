# Encrypted offline recovery

The existing operator CLI can export one stopped body, reconstruct it elsewhere and verify current authority before it can run. It never starts a service. Keep the founder public key independently of the backup, and keep the encrypted archive/checkpoint outside the original body's failure domain. Two directories in a Linux container test the software; they do not establish physical off-device custody.

The current scope is 512 regular files, 16 MiB of retained bytes and 4 MiB per file. Exceeding it refuses the export rather than omitting data. External read roots/deliveries, heartbeat and writer lock are excluded. Body-local credentials and private device/witness keys are encrypted. The founder private key should remain outside the body. Symlinks require an explicit operator migration. Use a strong unique encryption passphrase; it is entered through a hidden prompt and never a CLI argument.

Stop the authoritative source and wait for its process to release the ledger lock. The source must retain STOP:

```bash
python -m greg --home SOURCE stop --local
python -m greg --home SOURCE backup export --out /OFF_BODY/greg.encrypted \
  --checkpoint /OFF_BODY/authority.json --key /FOUNDER_KEY.pem
```

On the replacement, use the independently retained founder public key, not a key supplied by the archive. The destination must be new:

```bash
python -m greg --home NEW_BODY backup restore --archive /OFF_BODY/greg.encrypted \
  --checkpoint /OFF_BODY/authority.json --trusted-founder ROOT_PUBLIC_HEX
```

The output includes a `restore_challenge`. The new body has `RESTORE_PENDING`; phone commands, normal startup, local start and `--clear-stop` cannot make it executable. Obtain a fresh reference from the designated **current authoritative stopped source**, using that exact challenge:

```bash
python -m greg --home SOURCE backup checkpoint --challenge RESTORE_CHALLENGE \
  --out /OFF_BODY/fresh-authority.json --key /FOUNDER_KEY.pem
python -m greg --home NEW_BODY backup verify-authority \
  --checkpoint /OFF_BODY/fresh-authority.json --trusted-founder ROOT_PUBLIC_HEX
```

The fresh reference has a 15-minute window. Every durable file and ledger head must match. A source that gained a later revocation, pause, shutdown or any other durable change requires a new complete export; an old archive cannot be promoted by another signature. The verifier appends one canonical verification event and removes only its restoration guard. STOP/PAUSE, expired missions/grants, detached capabilities, revoked devices and used command nonces remain effective. Starting the replacement is a separate explicit local operator action, after retiring the old writer. Path-dependent read roots and delivery paths must be reviewed on replacement hardware; the software does not widen them or provision services.

If the source/current authority is unavailable, leave the replacement blocked. A historical authenticated archive proves retained bytes, not the absence of a newer revocation. This first path does not supply cross-body consensus/fencing and must not be used to run two independent authorities concurrently. Do not remove `RESTORE_PENDING` manually; it is a safety boundary rather than an ordinary pause. A failed partial destination remains guarded for diagnosis. The original stopped source is unchanged by export/restore.

Reproduce software qualification:

```bash
python -m pytest -q tests/unit/test_greg_backup.py tests/integration/test_greg_backup_restore.py
```

See [the two-pass decision and limits](../docs/collaboration/FOUNDRY-EXTRACTION-REVIEW-20261002.md) and [bound native evidence](../foundry/evidence/extraction-20261001/qualification-20261002.json). This capability is an increment toward the complete machine; remaining software work continues automatically.
