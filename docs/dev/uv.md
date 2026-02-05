# Building your cli tool with uv package manager

```bash
# Installing cli tool from main branch
uv tool install git+https://github.com/Cyber-Syntax/my-unicorn
# Example options:
#   -U, --upgrade:
#   Allow package upgrades, ignoring pinned versions in any existing output file. Implies `--refresh`
#
# Upgrade to tool from main branch
uv tool install --upgrade git+https://github.com/Cyber-Syntax/my-unicorn
```

Example: I installed tool via first command main branch(0.2.0-alpha), merged(0.3.0-alpha) the refactor/cleanup to main than update tool like below and it is perfectly updated the tool to new version.

```bash
uv tool install --upgrade git+https://github.com/Cyber-Syntax/my-unicorn
    Updated https://github.com/Cyber-Syntax/my-unicorn (5f30b5f8049621a0897fbaa47c759f4227f895a7)
      Built my-unicorn @ git+https://github.com/Cyber-Syntax/my-unicorn@5f30b5f8049621a0897fbaa47c759f4227f895a7
Updated my-unicorn v0.2.0a0 -> v0.3.0a0
 - my-unicorn==0.2.0a0 (from git+https://github.com/Cyber-Syntax/my-unicorn@55f0f6f705a08ff0f7c8985b84823372f992ea7c)
 + my-unicorn==0.3.0a0 (from git+https://github.com/Cyber-Syntax/my-unicorn@5f30b5f8049621a0897fbaa47c759f4227f895a7)
Installed 1 executable: my-unicorn
```
