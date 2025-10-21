---
title: Templates (Install & Update)
slug: templates
sidebar_label: Templates
toc: true
---

# Template system (Install / Update)

Purpose

- Describe the Template Method used for install/update flows.
- Show how templates are discovered and instantiated via factories and how to extend them.

Overview

- The template system provides pluggable strategies for installing and updating AppImages.
- Install-time and update-time behavior is implemented with template classes created by factory helpers.
- Install command uses `InstallTemplateFactory` and update command uses `UpdateTemplateFactory`.

Where the code lives

- Install templates and factory: [`my_unicorn/template/install/factory.py`](../my_unicorn/template/install/factory.py:1)  
- Update templates and factory: [`my_unicorn/template/update/factory.py`](../my_unicorn/template/update/factory.py:1)  
- High-level install usage: [`my_unicorn/commands/install.py:288`](../my_unicorn/commands/install.py:288)  
- Update handler usage: [`my_unicorn/commands/update.py:36`](../my_unicorn/commands/update.py:36)

Quick example — how InstallCommand uses the factory

- The CLI handler constructs an `InstallCommand` which builds shared dependencies and calls the template factory:

```python
# python
# See: [`my_unicorn/commands/install.py:275`](my_unicorn/commands/install.py:275)
url_template = InstallTemplateFactory.create_template("url", **dependencies)
url_results = await url_template.install(url_targets, **install_options)
```

Template factory API (conceptual)

- create_template(name: str, **dependencies) -> Template
    - name: template identifier (e.g., "url", "catalog")
    - dependencies: services such as download_service, storage_service, github_client, config_manager

Minimal template interface (observed usage)

```python
# python
class BaseInstallTemplate:
    async def install(self, targets: list[str], **options) -> list[dict]:
        """Install targets and return per-target results."""
```

Practical: Adding a new install template

1. Implement a template class under [`my_unicorn/template/install/`](../my_unicorn/template/install/:1) following the existing templates' shape (see examples in the folder).
2. Register the template in the factory (`create_template`) so it can be chosen by name.
3. Write unit tests mirroring existing tests under `tests/template/install/`.

Where installs and updates differ

- Install templates expect a list of targets (catalog names or URLs) and produce install results; they're created in the flow at [`my_unicorn/commands/install.py:288`](../my_unicorn/commands/install.py:288).
- Update templates operate on an `UpdateContext` object created in the update handler (`my_unicorn/commands/update.py:64`), and return structured `UpdateResult` objects. See `UpdateContext` definition at [`my_unicorn/models/update.py`](../my_unicorn/models/update.py:1).

Realistic usage examples tied to code

- Install from URL:
    - Factory call: [`my_unicorn/commands/install.py:286`](../my_unicorn/commands/install.py:286)
    - Template method: `install(targets, **install_options)` — implementation in concrete template classes under [`my_unicorn/template/install/`](../my_unicorn/template/install/:1)

- Update selected apps:
    - Handler builds context: [`my_unicorn/commands/update.py:64`](../my_unicorn/commands/update.py:64)
    - Factory call: [`my_unicorn/commands/update.py:36`](../my_unicorn/commands/update.py:36)

Testing

- Unit tests for templates live under `tests/template/`. Run them with:

```bash
source .venv/bin/activate
pytest -q tests/template/ -q
```

Troubleshooting & common pitfalls

- Factory not finding a template: confirm the template name is registered in the respective `factory.py` implementation (`my_unicorn/template/install/factory.py:1`).
- Incorrect dependencies: templates expect specific services (download_service, storage_service, github_client, config_manager). If you get attribute errors, ensure the factory is supplied the full `dependencies` mapping as shown in [`my_unicorn/commands/install.py:275`](../my_unicorn/commands/install.py:275).

Cross references

- CLI mapping: [`docs/cli.md`](../docs/cli.md:1)  
- Install handler: [`my_unicorn/commands/install.py:392`](../my_unicorn/commands/install.py:392)  
- Update handler and context: [`my_unicorn/commands/update.py:64`](../my_unicorn/commands/update.py:64)  
- Template install directory: [`my_unicorn/template/install/`](../my_unicorn/template/install/:1)  
- Template update directory: [`my_unicorn/template/update/`](../my_unicorn/template/update/:1)

End of template guide
