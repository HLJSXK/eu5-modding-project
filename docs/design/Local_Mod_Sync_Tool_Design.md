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

1. Host mode
- Command: `eu5-modsync host`
- Scans local `game/mod`
- Creates snapshot manifest
- Serves metadata and mod packages over HTTP

2. Client mode
- Command: `eu5-modsync sync`
- Pulls manifest from host URL
- Computes plan
- Applies sync to local `game/mod`
- Writes state file

Optional dry run:
- `eu5-modsync sync --dry-run`

## 4. High-Level Architecture

### Host Components
- Scanner: inventory local mods and file hashes
- Packager: per-mod zip package (or direct file stream in v2)
- Manifest Builder: snapshot metadata + hashes
- HTTP Server: serves manifest and package files

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

### v1 (trusted LAN)
- HTTP + one-time token
- Token passed in header `X-ModSync-Token`

### v1.1 (recommended)
- HTTPS reverse proxy (Caddy/Nginx) in front of host tool
- Short-lived token per sync session

### Manifest integrity
- Include manifest signature support (Ed25519)
- Client embeds trusted public key (or prompts first-use trust)

## 9. CLI Design

### Host
- `eu5-modsync host --mod-path "C:/.../Europa Universalis V/game/mod" --bind ":17777" --token "..." --out "./.modsync_host"`

### Client
- `eu5-modsync sync --server "http://192.168.1.20:17777" --token "..." --mod-path "C:/.../Europa Universalis V/game/mod" --dry-run`
- `eu5-modsync sync --server "http://192.168.1.20:17777" --token "..." --mod-path "C:/.../Europa Universalis V/game/mod" --delete-managed-missing=true`

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
- `pkg/modsync/manifest.go`
- `pkg/modsync/scanner.go`
- `pkg/modsync/planner.go`
- `pkg/modsync/downloader.go`
- `pkg/modsync/applier.go`
- `pkg/modsync/state.go`
- `pkg/modsync/server.go`
- `pkg/modsync/report.go`

## 11. Implementation Plan

### Phase 1 (MVP)
- Host scan + snapshot.json generation
- Client fetch + plan + dry-run report
- No writes yet

### Phase 2
- Package download and apply
- Backup/rollback
- State file persistence

### Phase 3
- Conflict-aware sync (KeptLocal)
- Delete managed missing
- Full action summary

### Phase 4
- Signature verification
- Resume/retry + parallel downloads
- Better host auth and session tokens

## 12. Why this replaces manual publish

- Host machine is always the source of truth
- No need to upload every mod update to remote storage before teammates sync
- Clients converge to host snapshot with explicit conflict protection
- Repeatable and auditable sync output every run

## 13. Optional Future Upgrade

After local sync works, add a hybrid mode:
- Host tool can publish same snapshot to Tencent COS as fallback source
- Clients prefer host LAN source, then fallback to COS

This gives both convenience and reliability.
