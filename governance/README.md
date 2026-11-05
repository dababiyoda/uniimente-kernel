# governance/

`integrity/` is the **live constitutional-integrity tripwire**: it detects any
change to a protected artifact that Alfonso's enrolled founder key has not
authorized. It is the authoritative, machine-read list of protected files
(`governance/integrity/manifest.json`); read `integrity/README.md` before
touching anything it names.

```bash
python -m governance.integrity --check   # exit 0 clean, 1 finding, 2 unsound record
```

Runs in Canonical CI (authority job). It grants nothing: only a signature by an
enrolled founder key authorizes an artifact change.
