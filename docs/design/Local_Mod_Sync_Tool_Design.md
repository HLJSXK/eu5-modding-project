# Local Mod Sync Tool Design

## 1. Goal

Build a new tool that mirrors the source player's local EU5 mods to friends' local game state.

- Source of truth: host player's local `Europa Universalis V/game/mod`
- Target: each friend's local `Europa Universalis V/game/mod`
- Replace manual publishing workflows
- Keep explicit sync actions: Added, Updated, Deleted, KeptLocal

This is effectively the reverse of deployer packaging:
- deployer today: static assets -> target machine
- new sync tool: host local mods -> peers

## 2. Scope

### In Scope
- One host machine serves current mod snapshot
- Multiple client machines pull and synchronize
- Three-way conflict handling (remote snapshot, local current, local last-applied state)
- Action report output per mod and summary totals
- Resume/retry downloads

### Out of Scope (v1)
- Real-time bi-directional sync
- LAN P2P mesh
- Binary delta patches

## 3. Proposed Tooling

Add a new executable:

- `cmd/eu5-modsync/main.go`

Modes:

1. Publish mode
- Command: `eu5-modsync publish`
- Scans local `game/mod`
- Creates snapshot manifest and zip packages
- Supports optional COS upload and custom upload command

2. Sync mode
- Command: `eu5-modsync sync`
- Pulls manifest from URL (`--manifest-url`)
- Computes plan
- Applies sync to local `game/mod`
- Writes state file

Optional dry run:
- `eu5-modsync sync --dry-run`

## 4. High-Level Architecture

### Publish Components
- Scanner: inventory local mods and file hashes
- Packager: per-mod zip package
- Manifest Builder: snapshot metadata + hashes
- Uploader: optional COS or custom upload command

### Client Components
- Manifest Fetcher
- Planner (diff and conflict resolver)
- Downloader (retry/resume)
- Applier (atomic apply per mod)
- State Store (`.eu5-modsync-state.json`)
- Reporter (console + log)

## 5. Data Model

### 5.1 Snapshot Manifest (`snapshot.json`)

Fields:
- schema_version
- snapshot_id (timestamp + short digest)
- generated_at_utc
- host_name
- game_mod_rel_path (`game/mod`)
- mods: []

Per mod fields:
- mod_id (directory name)
- display_name
- version_hint (optional, from metadata if available)
- package_url
- package_sha256
- package_size
- content_hash (hash of normalized file manifest)
- file_count

### 5.2 Client State (`.eu5-modsync-state.json`)

Fields:
- schema_version
- last_snapshot_id
- last_sync_time_utc
- managed_mods: map[mod_id]

Per managed mod:
- last_applied_snapshot_id
- last_applied_content_hash
- last_applied_package_sha256

## 6. Sync Semantics

Target folder:
- `Europa Universalis V/game/mod`

Action classes:
- Added: exists in remote snapshot, absent locally
- Updated: exists both sides, remote differs, no local divergence
- Deleted: previously managed local mod no longer in remote snapshot
- KeptLocal: local diverged from last-applied state, keep local copy
- UnmanagedLocal: local mod not managed by tool, untouched

### Three-way decision (important)

For each mod_id:
1. Remote hash from snapshot
2. Local current hash from disk
3. Local last-applied hash from state file

Rules:
- If remote missing and mod is managed -> Deleted
- If local missing and remote exists -> Added
- If remote == local -> NoOp
- If local == last_applied and remote != local -> Updated
- If local != last_applied and remote != local -> KeptLocal

This avoids overwriting user-edited mods while still enabling deterministic sync.

## 7. Apply Strategy

Per mod transactional apply:
1. Download package to temp
2. Verify SHA-256
3. Extract to temp staging dir
4. Backup existing target mod dir to `.modsync_backup/<mod_id>/<time>`
5. Replace target dir (rename/swap)
6. Update state file

If apply fails, restore from backup.

## 8. Transport and Security

### v1 (implemented)
- Static HTTP/HTTPS manifest URL with package links
- Optional COS upload for remote distribution

### Recommended
- Host snapshot files over HTTPS (CDN/Object Storage)
- Use short-lived credentials for publish and upload

## 9. CLI Design

### Publish
- `eu5-modsync publish --mod-path "C:/.../Europa Universalis V/game/mod" --out ".modsync_publish" --base-url "https://cdn.example.com/modsync"`
- `eu5-modsync publish --mod-path "C:/.../game/mod" --cos-bucket mybucket-1250000000 --cos-region ap-shanghai --cos-prefix modsync`

### Sync
- `eu5-modsync sync --manifest-url "https://cdn.example.com/modsync/snapshot.json" --mod-path "C:/.../Europa Universalis V/game/mod" --dry-run`
- `eu5-modsync sync --manifest-url "https://cdn.example.com/modsync/snapshot.json" --mod-path "C:/.../Europa Universalis V/game/mod" --delete-managed-missing=true`

### Output report
- Snapshot ID
- Added list
- Updated list
- Deleted list
- KeptLocal list
- UnmanagedLocal list
- Failed list
- Summary totals

## 10. Suggested Repository Layout

- `cmd/eu5-modsync/main.go`
- `pkg/modsync/client.go`
- `pkg/modsync/host.go`
- `pkg/modsync/cos_upload.go`
- `pkg/modsync/types.go`

## 11. Implementation Plan

### Status
- Publish + sync core flow implemented
- Conflict-aware plan and state file implemented
- COS upload path implemented
- Optional signature/auth hardening remains future work

## 12. Why this replaces manual publish

- Host machine is always the source of truth
- No need to upload every mod update to remote storage before teammates sync
- Clients converge to host snapshot with explicit conflict protection
- Repeatable and auditable sync output every run

## 13. Optional Future Upgrade

Hybrid mode is now effectively available through publish + COS upload:
- Host machine can publish snapshot and packages to Tencent COS
- Clients sync from the published manifest URL

This gives both convenience and reliability.
