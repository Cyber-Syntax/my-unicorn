---
title: Catalog format
slug: catalog-format
sidebar_label: Catalog
toc: true
---

# Catalog JSON format

Purpose

- Document the bundled catalog schema used by the CLI to install apps from names.
- Provide examples taken from actual catalog entries in the repository and explain how the CLI maps catalog fields to behavior.

Quickstart

```bash
# Install an app from the bundled catalog by name
my-unicorn install appflowy
```

Where to find catalog files

- Bundled catalog directory: [`my_unicorn/catalog/`](../my_unicorn/catalog/:1)  
- Example entry: [`my_unicorn/catalog/appflowy.json`](../my_unicorn/catalog/appflowy.json:1)

Catalog entry schema (high level)

- owner (string): GitHub owner or organization
- repo (string): GitHub repository name
- appimage (object):
    - rename (string): friendly base name used when renaming downloaded AppImage
    - name_template (string): template used to format final filename
    - characteristic_suffix (array[string]): preferred suffixes for filenames
- github (object):
    - repo (bool): whether this entry maps to a GitHub repository releases API
    - prerelease (bool): whether to prefer prerelease/beta releases
- verification (object):
    - digest (bool): whether GitHub asset digest is expected
    - skip (bool): skip verification
    - checksum_file (string): optional checksum file name
    - checksum_hash_type (string): e.g. "sha256"
- icon (object | null):
    - extraction (bool): extract icon from AppImage when installed
    - url (string): optional direct URL to icon (raw.githubusercontent)
    - name (string): filename to save icon as

Example catalog entry (short)

```json
{
  "owner": "AppFlowy-IO",
  "repo": "AppFlowy",
  "appimage": {
    "rename": "AppFlowy",
    "name_template": "{rename}-{latest_version}-linux-{characteristic_suffix}.AppImage",
    "characteristic_suffix": [""]
  },
  "github": {"repo": true, "prerelease": false},
  "verification": {"digest": true, "skip": false, "checksum_file": "", "checksum_hash_type": ""},
  "icon": {"extraction": true, "url": "", "name": "appflowy.svg"}
}
```

How the code uses the catalog

- Catalog files are read by [`CatalogManager.load_catalog_entry()`](../my_unicorn/config.py:826) in [`my_unicorn/config.py`](../my_unicorn/config.py:814).  
- The installer uses catalog metadata to:
    - determine owner/repo for GitHub API queries (see [`my_unicorn/github_client.py`](../my_unicorn/github_client.py:1)),
    - choose whether to fetch prerelease assets,
    - determine verification strategy (`verification` fields used by verification services at [`my_unicorn/verification/`](../my_unicorn/verification/:1)),
    - extract or download icons (`icon` fields used by [`my_unicorn/services/icon_service.py`](../my_unicorn/services/icon_service.py:1)).

Validation tips

- Ensure `owner` and `repo` are correct GitHub identifiers.
- If a project provides asset digests in GitHub releases, set `verification.digest = true`.
- If the AppImage filename differs from the repo name, use `appimage.rename` and `name_template` to ensure consistent installed filenames.

Real-world example (link)

- Inspect the AppFlowy catalog file: [`my_unicorn/catalog/appflowy.json`](../my_unicorn/catalog/appflowy.json:1)

Troubleshooting

- If installation from catalog fails with "catalog entry not found", confirm the file exists in the bundled catalog and that the catalog directory is validated at startup (`DirectoryManager.validate_catalog_directory()` — see [`my_unicorn/config.py`](../my_unicorn/config.py:318)).
- If verification fails, check `verification.checksum_file` and `checksum_hash_type` values in the catalog entry; some projects provide external checksum files instead of asset `digest`.

Minimal reproducible check

- Programmatically load and print a catalog entry:

```python
# python
from my_unicorn.config import ConfigManager
cfg = ConfigManager()
entry = cfg.load_catalog_entry("appflowy")
print(entry)
```

Cross references

- CLI reference: [`docs/cli.md`](../docs/cli.md:1)  
- Configuration: [`docs/configuration.md`](../docs/configuration.md:1)  
- Verification services: [`my_unicorn/verification/verify.py`](../my_unicorn/verification/verify.py:1)
