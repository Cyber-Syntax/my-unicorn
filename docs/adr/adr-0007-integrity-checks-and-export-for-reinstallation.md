---
title: "ADR-0007: Integrity Checks and Export Command for Cross-Distro Reinstallation"
status: "Proposed"
date: "2026-03-01"
authors: "Cyber-Syntax"
tags: ["architecture", "decision", "integrity", "export", "install", "migration"]
supersedes: ""
superseded_by: ""
---

## Status

**Proposed**

## Context

My-unicorn currently determines whether an app is "installed" by checking if a JSON config file exists in `~/.config/my-unicorn/apps/`. This check is shallow — it does not verify that the actual AppImage binary, `.desktop` entry, or icon file physically exist on disk. The only place a filesystem existence check occurs is in `InstallApplicationService._build_install_plan()`, where `installed_path.exists()` is tested to skip already-installed catalog apps. No equivalent check exists for desktop entries or icons.

This creates several problems:

1. **Silent corruption / orphaned configs**: If a user deletes an AppImage manually, or if a file becomes corrupted, my-unicorn still considers the app installed because the JSON config exists. Subsequent `update` commands may fail with confusing errors instead of guiding the user to reinstall.

2. **No `.desktop` or icon verification**: Even when the AppImage binary is checked, the corresponding desktop entry (`~/.local/share/applications/<app>.desktop`) and icon file are never verified. A missing desktop entry means the app won't appear in the application launcher, but my-unicorn won't report this.

3. **Cross-distro migration is manual and error-prone**: When a user switches to a new Linux distribution and copies their `~/.config/my-unicorn/` directory, my-unicorn configs reference AppImages, icons, and desktop entries that no longer exist on the new system. There is no built-in mechanism to reinstall all previously-installed applications from scratch. Users must manually remember and re-run individual `install` commands. Even if user try to update apps after copying config, it would always show up-to-date because it only check the config file, not the actual files. This is a poor user experience and can lead to confusion and frustration.

4. **Batch install from config is not supported**: The `install` command supports multiple targets (`install app1 app2 ...`), but there is no way to export the list of currently installed apps and replay it on another machine. Also URL installed apps cannot be reinstalled with catalog apps together since they require different install commands (`install <name>` vs `install <url>`). We save repo name and app name on also url installed apps, but we need to add the github url on install command, so we either need to save the url on config or we need to get repo name and app name and integrate it the github url like `https://www.github.com/<repo_owner>/<repo_name>` to be able to reinstall url apps with the same command as catalog apps, but it would require some parsing and integration logic to construct the correct URL for each app. Maybe it is better to save url directly to config to avoid this complexity and make the export/reinstall workflow simpler.

5. **`list_installed_apps()` only checks filenames**: `AppConfigManager.list_installed_apps()` globs `*.json` in the apps directory. It does not distinguish between healthy installations and stale/orphaned configs. This also means that when user sync the config to a new system, all apps will be listed as installed even though their files are missing.

## Decision

Introduce two complementary features:

### 1. Installation Integrity Checks

Add a `doctor` (or `check`) subcommand and integrate lightweight integrity checks into existing workflows:

- **`my-unicorn doctor`**: Scans all app configs and verifies that the AppImage binary, `.desktop` entry, and icon file exist at the paths recorded in each app's state config. Reports a per-app health status (healthy / corrupt / broken).
- **Update/list integration**: Before performing an update, verify the AppImage exists. In `catalog --installed` output, flag apps whose files are missing.
- **No automatic repair**: The doctor command reports problems but does not auto-fix them. Users can then `remove` the broken app and `install` it again, or use the export/reinstall workflow below.
- **verify-sha**: Apps config has checksums of the file if it isn't "skipped" for verification, so we can also verify the integrity of the AppImage file itself and report if it is corrupted.

### 2. Export Command for Bulk Reinstallation

Add a `my-unicorn export` subcommand that writes the list of currently installed apps to stdout or a file, separated by source type:

- **Catalog apps**: Exported as plain app names (one per line), since they can be reinstalled via `my-unicorn install <name1> <name2> ...`.
- **URL apps**: Exported as the original GitHub release URLs stored in the app's `overrides.source` config, since they require `my-unicorn install <url>`.
- **Output format**: Simple newline-delimited text files (e.g., `catalog-apps.txt` and `url-apps.txt`), not JSONL. This keeps the export human-readable, easily editable, and directly usable as CLI arguments.
- **Reinstall workflow**: On the new system, the user runs:

  ```bash
  my-unicorn install $(cat catalog-apps.txt)
  my-unicorn install $(cat url-apps.txt)
  ```

This approach avoids introducing a new JSONL database format. The existing per-app JSON configs remain the single source of truth, and the export is a lightweight derived artifact.

### 3. AppImage integrity verification

- **Verify SHA**: Add an `--verify-sha` flag to the `doctor` command that checks the SHA256 checksum of each AppImage against the value stored in the app's config (if available). This would allow users to detect corrupted or tampered AppImage files, not just missing ones.
- **Update Integration**: If integrity verification is added, consider integrating it into the update process as well. If an AppImage fails the integrity check during an update, prompt the user to reinstall instead of attempting to update a potentially corrupted file.
- **Limitations**: Some apps may not have checksums available (e.g dev's not providing them, or user overrides that skip verification). In these cases, the doctor command can report "verification skipped" but still check for file existence. Maybe we could add checksums only for the appimage to ensure the binary integrity, but not for desktop entry and icon since they are generated and don't have a source of truth for checksum.

## Consequences

### Positive

- **POS-001**: Detects orphaned configs and missing binaries early, providing clear error messages instead of cryptic failures during update.
- **POS-002**: Verifying `.desktop` and icon files gives users confidence that their app launcher integration is intact.
- **POS-003**: The `export` command enables a simple, repeatable cross-distro migration workflow without requiring a separate database.
- **POS-004**: Separating catalog and URL exports means each list can be fed directly to the existing `install` command with no new install mode required.
- **POS-005**: No new storage format — avoids the complexity and maintenance burden of a JSONL database layer.

### Negative

- **NEG-001**: The `doctor` command adds a new subcommand and associated test surface. Integrity checks must be kept fast to avoid slowing down the CLI.
- **NEG-002**: Filesystem existence checks add I/O. For users with many installed apps, iterating all configs and checking multiple paths per app introduces latency (mitigated by async I/O).
- **NEG-003**: Export only captures app names and URLs — it does not preserve user overrides, custom verification settings, or icon configuration. Reinstalled apps will use current catalog defaults.
- **NEG-004**: URL apps may break if the original GitHub release URL is no longer valid (e.g., repository renamed or deleted).

## Alternatives Considered

### JSONL Database for Installed Apps

- **ALT-001**: **Description**: Introduce a `.jsonl` file that mirrors the installed apps directory, storing one JSON object per line with full app metadata for fast bulk operations and portability.
- **ALT-002**: **Rejection Reason**: This duplicates data already stored in per-app JSON configs, creating a synchronization problem. Every install, update, and remove operation would need to update both the JSON config and the JSONL file. The added complexity is not justified when the export command can derive the same information on demand.

### Automatic Repair in Doctor Command

- **ALT-003**: **Description**: Have the `doctor` command automatically reinstall or repair broken apps (e.g., re-download missing AppImages, regenerate desktop entries).
- **ALT-004**: **Rejection Reason**: Automatic repair requires network access, user consent for downloads, and handling of partial failures — significantly increasing complexity. Reporting problems and letting users choose to reinstall via `install` or `remove` + `install` is safer and more transparent.

### Single Combined Export File

- **ALT-005**: **Description**: Export both catalog and URL apps into a single file with a prefix or marker to distinguish them (e.g., `catalog:appname` or `url:https://...`).
- **ALT-006**: **Rejection Reason**: A custom format requires parsing logic and is not directly usable as `install` command arguments. Separate plain-text files are simpler and can be used with shell expansion (`$(cat file.txt)`) without any processing.

### Do Nothing

- **ALT-007**: **Description**: Rely on the current behavior where app existence is determined solely by JSON config presence.
- **ALT-008**: **Rejection Reason**: This leaves users with no way to detect stale installations or efficiently migrate to a new system. The current behavior produces confusing errors when files are missing and forces manual tracking of installed apps for migration.

## Implementation Notes

- **IMP-001**: Add a `doctor` subcommand in `cli/commands/doctor.py` that iterates `AppConfigManager.list_installed_apps()`, loads each config via `load_app_config()`, and checks `Path.exists()` for `installed_path`, the desktop entry path (`~/.local/share/applications/<app>.desktop`), and the icon path from state config.
- **IMP-002**: Add an `export` subcommand in `cli/commands/export.py` that loads all app configs, partitions them by `source` field (`"catalog"` vs `"url"`), and writes app names or URLs to stdout or specified output files.
- **IMP-003**: For the `doctor` command, define health status levels: **healthy** (all files present), **corrupt** (AppImage exists but desktop/icon missing), **broken** (AppImage missing). Display a summary table.
- **IMP-004**: Integrate a lightweight AppImage existence check into `UpdateHandler` — if the binary referenced by config does not exist, warn the user and suggest reinstalling instead of attempting an update.
- **IMP-005**: Add `--output-dir` flag to `export` for specifying where to write the export files. Default to stdout for piping flexibility.
- **IMP-006**: Consider adding `--format` flag to `export` in the future for JSON output, but start with plain text for simplicity.

## References

- **REF-001**: [adr-0004-remove-all-command.md](adr-0004-remove-all-command.md) — Related pattern for bulk operations across all installed apps.
- **REF-002**: [AppConfigManager.list_installed_apps()](../../src/my_unicorn/config/app.py) — Current implementation that checks only for JSON file existence.
- **REF-003**: [InstallApplicationService._build_install_plan()](../../src/my_unicorn/core/services/install_service.py) — Only place where `installed_path.exists()` is currently checked.
- **REF-004**: [types.py — AppStateConfig](../../src/my_unicorn/types.py) — Type definition showing `state.installed_path`, `state.icon.path`, and `source` field used to distinguish catalog vs URL apps.
