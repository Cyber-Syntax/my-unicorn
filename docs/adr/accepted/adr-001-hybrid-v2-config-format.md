---
title: "ADR-0001: Hybrid v2 Configuration Format - Source-Aware Storage"
status: "Accepted"
date: "2026-02-03"
authors: "Development Team"
tags: ["architecture", "decision", "configuration", "storage"]
supersedes: ""
superseded_by: ""
---

# ADR-0001: Hybrid v2 Configuration Format - Source-Aware Storage

## Status

**Accepted** (Implemented in v2.0.0)

## Context

The my-unicorn application manages AppImage installations from two distinct sources:

1. **Catalog apps**: Pre-defined applications in bundled JSON catalog files (`src/my_unicorn/catalog/*.json`)
2. **URL apps**: Custom installations from GitHub release URLs provided by users

In the v1.0.0 configuration format, all installed applications stored complete configuration metadata in per-app JSON files (`~/.config/my-unicorn/apps/*.json`), regardless of installation source. This approach had several drawbacks:

- **Duplication**: Catalog apps duplicated all metadata (display name, description, GitHub owner/repo, verification method, icon method) that already existed in catalog files
- **Storage Inefficiency**: Each catalog app config consumed ~500 bytes when only ~125 bytes of state was unique
- **Maintenance Burden**: Catalog metadata updates required manual migration or re-installation to propagate changes
- **No Single Source of Truth**: Catalog files and app configs could diverge, causing confusion
- **Semantic Ambiguity**: The configuration structure didn't distinguish between catalog-managed and user-managed apps

The configuration system needed to evolve to:

- Eliminate redundant storage for catalog apps
- Establish catalog as the authoritative source for catalog app metadata
- Preserve self-containment for URL apps (no catalog dependency)
- Enable automatic propagation of catalog updates to installed apps
- Reduce storage and memory footprint for typical installations (5-10 catalog apps)

Technical constraints:

- Must maintain backward compatibility through migration tooling
- Must preserve validation guarantees at load/save boundaries
- Must support runtime merging without performance degradation
- Must handle mixed environments (catalog + URL apps)

## Decision

Implement a **source-aware hybrid configuration format (v2.0.0)** where the storage strategy adapts to the installation source:

**For Catalog Apps**:

- Store only **state** (version, install date, paths, verification results) + **catalog reference** in app config
- Reference catalog file via `catalog_ref` field (e.g., `"catalog_ref": "appflowy"` → `catalog/appflowy.json`)
- Eliminate metadata duplication in app configs
- At runtime, merge catalog entry + state via `get_effective_config()` to produce complete configuration

**For URL Apps**:

- Store complete configuration in **overrides** section (metadata, source, appimage, verification, icon)
- Remain fully self-contained without catalog dependency
- Set `catalog_ref` to `null` to indicate no catalog association

**Rationale**:

- **DRY Principle**: Catalog metadata changes automatically propagate to all installed catalog apps without migration
- **Storage Efficiency**: ~75% size reduction for catalog apps (500 bytes → 125 bytes)
- **Single Source of Truth**: Catalog is authoritative for metadata; state tracks installation-specific data
- **Self-Contained URL Apps**: URL installations don't depend on catalog, remain portable and independent
- **Clear Semantics**: `source` field ("catalog" vs "url") explicitly distinguishes app management model

## Consequences

### Positive

- **POS-001**: **Storage Reduction**: Catalog app configs shrink by ~75% (500 bytes → 125 bytes), reducing disk usage and JSON parsing overhead for typical installations with 5-10 apps
- **POS-002**: **Automatic Metadata Updates**: Catalog updates (display names, descriptions, verification methods, icon methods) automatically propagate to all installed catalog apps without manual migration or re-installation
- **POS-003**: **Clear Separation of Concerns**: Source-aware structure (`source: "catalog"` vs `source: "url"`) explicitly separates catalog-managed apps (reference-based) from user-managed apps (self-contained)
- **POS-004**: **Reduced Memory Footprint**: In-memory app configs consume less memory during batch operations (update, list, migrate)
- **POS-005**: **Simplified Config Backups**: Backup files are smaller and cleaner, containing only installation state rather than duplicated metadata
- **POS-006**: **Consistency Guarantees**: Catalog apps always use current catalog metadata, eliminating drift between catalog and installed apps

### Negative

- **NEG-001**: **Breaking Change**: v1.0.0 configs are incompatible with v2.0.0, requiring mandatory migration via `my-unicorn migrate` command on first run after upgrade
- **NEG-002**: **Increased Runtime Complexity**: Config loading requires three-layer merge logic (Catalog → State → Overrides) instead of simple file deserialization, adding ~5-10ms overhead per app load
- **NEG-003**: **Catalog Dependency**: Catalog apps cannot operate if catalog file is missing or corrupted (mitigated by bundled catalog distribution in package)
- **NEG-004**: **Migration Burden**: Users must run migration tool on upgrade, potentially causing confusion if skipped or failed
- **NEG-005**: **Debugging Complexity**: Effective config is computed at runtime rather than stored, requiring inspection of multiple files (catalog + state) to understand actual configuration
- **NEG-006**: **Testing Complexity**: Tests must verify merge logic across multiple layers and handle both catalog and URL app scenarios

## Alternatives Considered

### Full Duplication (v1.0.0 Approach)

- **ALT-001**: **Description**: Store complete configuration for all apps regardless of source (catalog or URL)
- **ALT-002**: **Rejection Reason**: Violates DRY principle, wastes storage (~375 bytes per catalog app), and eliminates single source of truth. Catalog updates require manual migration or re-installation to propagate.

### Always Reference Catalog

- **ALT-003**: **Description**: Store only references for both catalog and URL apps, creating catalog entries dynamically for URL installations
- **ALT-004**: **Rejection Reason**: URL apps would lose self-containment and become dependent on catalog files. Creates unnecessary coupling and complicates uninstallation (must clean up dynamically-created catalog entries).

### Hybrid with Periodic Sync

- **ALT-005**: **Description**: Store full config for both sources but periodically sync catalog app configs from catalog files
- **ALT-006**: **Rejection Reason**: Introduces eventual consistency issues (state between syncs is undefined), adds complexity with sync scheduling/triggers, and still duplicates storage during normal operation. Merge-on-read (v2.0.0 approach) is simpler and provides immediate consistency.

### Symlink-Based Sharing

- **ALT-007**: **Description**: Use filesystem symlinks from app configs to catalog files to share metadata
- **ALT-008**: **Rejection Reason**: Platform-dependent (symlinks unreliable on Windows), fragile (broken links on catalog reorganization), and doesn't solve the semantic separation problem. JSON-based references are more portable and explicit.

## Implementation Notes

- **IMP-001**: **Three-Layer Merge Strategy**: `get_effective_config()` merges Catalog (base) → State → Overrides (priority), with later layers overriding earlier ones. Catalog apps ignore overrides; URL apps skip catalog layer.
- **IMP-002**: **Lazy Catalog Loading**: Catalog files are loaded only when needed (on-demand) to minimize startup overhead. Catalog is cached in memory during batch operations (update, list).
- **IMP-003**: **Schema Validation Boundaries**: Validate merged effective config before use (ensures runtime config meets schema requirements). Validate state and overrides independently before save (ensures stored data is well-formed).
- **IMP-004**: **Backup-First Migration**: Migration tool (`my-unicorn migrate`) creates timestamped backups in `~/.config/my-unicorn/apps/backups/` before modifying configs, enabling rollback on failure.
- **IMP-005**: **Version Detection**: Migration is triggered automatically on first run after upgrade by comparing `config_version` field in app configs against `APP_CONFIG_VERSION` constant ("2.0.0").
- **IMP-006**: **Graceful Degradation**: If catalog file is missing for a catalog app, log warning and skip the app rather than failing the entire operation. Suggest re-installation to fix.
- **IMP-007**: **Success Criteria**: Migration completes successfully for all apps, no data loss, catalog apps load and update correctly, URL apps remain independent of catalog.

## References

- **REF-001**: [docs/config.md](../../dev/config.md) - Detailed configuration format documentation
- **REF-002**: [src/my_unicorn/config/app.py](../../src/my_unicorn/config/app.py) - App config implementation with `get_effective_config()`
- **REF-003**: [src/my_unicorn/config/catalog.py](../../src/my_unicorn/config/catalog.py) - Catalog loader implementation
- **REF-004**: [src/my_unicorn/config/migration/app_config.py](../../src/my_unicorn/config/migration/app_config.py) - v1→v2 migration logic
- **REF-005**: [src/my_unicorn/constants.py](../../src/my_unicorn/constants.py) - `APP_CONFIG_VERSION = "2.0.0"`
- **REF-006**: [tests/test_config_migration.py](../../tests/test_config_migration.py) - Migration test suite
- **REF-007**: [AGENTS.md](../../AGENTS.md) - Development guidelines emphasizing DRY, KISS, YAGNI principles
