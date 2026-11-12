# Verifying the intake mission's verdicts outside the envelope (2026-11-12, 15:00-15:09 UTC)

The mission ran under the `supervised` floor (bubblewrap absent; network denied by seccomp; Landlock; temp
directory inside the clone). Each verdict below was re-checked by the session with plain pytest on an archive of
the exact head, outside that envelope.

| Unit | Mission verdict | File | Own head outside the envelope |
|---|---|---|---|
| 291 `41fcc41f` | hold: own test fails | tests/unit/test_greg_egress.py | 16 passed |
| 273 `331de165` | hold: own test fails | tests/unit/test_greg_background_dispatch.py | 17 passed |
| 294 `1643932e` | hold: own test fails | tests/unit/test_greg_retained_receipt.py | 39 passed (also 39 passed under `unshare -rn`) |
| 300 `b1f157fe` | hold: own test fails | tests/unit/test_greg_retained_receipt.py | same file as 294 |
| 293 `32ca8de7` | hold: own test fails | tests/unit/test_greg_browser.py | 3 passed |

Behavioural conflict 291 + 273, outside the envelope, merge of 41fcc41f into 331de165:
`tests/unit/test_greg_background_dispatch.py` 13 failed, 4 passed (364.77 s). The mission reported 7 as conflicts
(cause 291, correct) and 6 as failing before the merge. The same 13/4 split is recorded in commit fbb3bcf8
(2026-11-11), which resolves it on the composed candidate.

Causes reproduced with `greg.workers.run_tests(..., confinement="supervised")` on the intake branch:
- 293: fixture `_port()` calls `socket.socket()`: `PermissionError: [Errno 1] Operation not permitted` at setup.
- 294/300: `tmp_path` is `<head>/.greg-tmp-*/pytest-of-root/...`, inside the clone; the test's expected refusal
  text `path <tmp>/outside.txt outside permitted roots` does not match the full path the run produced.
