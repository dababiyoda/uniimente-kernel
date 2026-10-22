# Fresh-entry rehearsal handoff

Evidence tier: sandbox multi-agent rehearsal, not external Claude adoption.

Producer: /root/fresh_entry. Coordinator: /root. Independent code reviewer:
/root/verify_rollout. Producer started with this partial package's CLAUDE.md,
followed AGENTS.md and START_HERE.md, and inspected live issue #96 and draft #193.
Observed remote head: 66e4d3d985e39215c8e3e8ba1cc39103cc9a6c37; base:
d64a6c931bb05aba4e3454847b665e73384bbdfa. Local changes are not that published head.

Collision: coordinator owns RECEIPT.md and START_HERE.md. Producer acknowledged
read-only example review, then coordinator explicitly acknowledged that split.
Producer made no edits; independent validation retained a separate worker.

Producer recommended blocked/split and pending/accepted examples, a fresh UTC
recheck placeholder, and honest unavailable-source handling. Coordinator applied
those documentation changes. Discussion #89 retrieval returned HTTP 400 through
the connector for the producer; it did not claim to have read the body. The
coordinator had read it in the earlier browser inspection. New source access is
still not evidence that every existing session has refreshed instructions.

Receiver task: inspect RECEIPT.md and run the exact checker tests from this partial
package; verify the recommended examples and corrected outer four-backtick fence.
Report actual result, source limitations, next adoption step and any remaining
defect without editing files or contacting other repositories. Acknowledge this
handoff to the coordinator. No founder reconstruction is needed for that task.

Stop condition: do not merge, update Discussions, execute product runtime or
represent this sandbox as actual Claude startup/hook verification. The final
published commit will be recorded in PR #193 after validation.
