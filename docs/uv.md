# Building your cli tool with uv package manager

```bash
# Installing cli tool from main branch
uv tool install git+https://github.com/Cyber-Syntax/auto-penguin-setup
# Installing cli tool from refactor/cleanup branch
uv tool install git+https://github.com/Cyber-Syntax/auto-penguin-setup@refactor/cleanup
# Upgrade to tool from main branch
uv tool upgrade auto-penguin-setup
```

Example: I installed tool via first command main branch(0.2.0-alpha), merged(0.3.0-alpha) the refactor/cleanup to main than update tool like below and it is perfectly updated the tool to new version.

```bash
uv tool upgrade auto-penguin-setup
    Updated https://github.com/Cyber-Syntax/auto-penguin-setup (5f30b5f8049621a0897fbaa47c759f4227f895a7)
      Built auto-penguin-setup @ git+https://github.com/Cyber-Syntax/auto-penguin-setup@5f30b5f8049621a0897fbaa47c759f4227f895a7
Updated auto-penguin-setup v0.2.0a0 -> v0.3.0a0
 - auto-penguin-setup==0.2.0a0 (from git+https://github.com/Cyber-Syntax/auto-penguin-setup@55f0f6f705a08ff0f7c8985b84823372f992ea7c)
 + auto-penguin-setup==0.3.0a0 (from git+https://github.com/Cyber-Syntax/auto-penguin-setup@5f30b5f8049621a0897fbaa47c759f4227f895a7)
Installed 1 executable: aps
```
