# UI Documentation

Welcome to the UI documentation for my-unicorn! This guide shows you what the command-line interface looks like during different operations. Each example demonstrates real output, so you can see exactly what happens when you run commands.

## Installation Examples

### With Warnings

Sometimes apps don't provide checksums for verification. Here's what that looks like:

#### Example: Installing an app without checksums

```bash
my-unicorn install weektodo
```

**Output:**

```
Fetching from API:
GitHub Releases      1/1 Retrieved from cache

Downloading:
WeekToDo-2.2.0  108.6 MiB  11.2 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying weektodo ⚠
    not verified (dev did not provide checksums)
(2/2) Installing weektodo ✓

📦 Installation Summary:
--------------------------------------------------
weektodo                  ✅ 2.2.0
                             ⚠️  Not verified - developer did not provide checksums

🎉 Successfully installed 1 app(s)
⚠️  1 app(s) installed with warnings
```

#### Example: Installing from a GitHub URL with partial verification

```bash
my-unicorn install https://github.com/Legcord/Legcord
```

**Output:**

```
Fetching from API:
GitHub Releases      1/1 Retrieved

Downloading:
Legcord-1.2.1-linux-x86_64  139.5 MiB  10.7 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying legcord ✓
(2/2) Installing legcord ✓

📦 Installation Summary:
--------------------------------------------------
legcord                   ✅ 1.2.1
                             ⚠️  Partial verification: 2 passed, 1 failed

🎉 Successfully installed 1 app(s)
⚠️  1 app(s) installed with warnings
```

### Without Warnings

When everything verifies perfectly, you get clean output.

#### Example: Fresh install from API

```bash
my-unicorn install qownnotes
```

**Output:**

```
Fetching from API:
GitHub Releases      1/1 Retrieved

Downloading:
QOwnNotes-x86_64   41.6 MiB  19.8 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓

📦 Installation Summary:
--------------------------------------------------
qownnotes                 ✅ 26.2.0

🎉 Successfully installed 1 app(s)
```

## Update Examples

Updates show version changes and use cached data when available.

#### Example: Updating an app

```bash
my-unicorn update qownnotes
```

**Output:**

```
Fetching from API:
GitHub Releases      1/1 Retrieved from cache

Downloading:
QOwnNotes-x86_64   41.6 MiB   8.7 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓

📦 Update Summary:
--------------------------------------------------
Successfully updated qownnotes
qownnotes                 ✅ 0.1.0 → 26.2.0

🎉 Successfully updated 1 app(s)
```

#### Example may still building

- This happens when the release is new and the AppImage asset hasn't finished building yet.

```bash
Fetching from API:
GitHub Releases      2/2 Retrieved from cache

Downloading:
helium-0.10.2.1-x86_64  143.9 MiB  10.8 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying helium-linux ✓
(2/2) Installing helium-linux ✓


📦 Update Summary:
--------------------------------------------------
helium-linux              ✅ 0.9.4.1 → 0.10.2.1
nuclear                   ❌ Update failed
                             → AppImage not found in release - may still be building

🎉 Successfully updated 1 app(s)
❌ 1 app(s) failed to update
✓ All outdated apps updated successfully
```

## Remove Examples

Removing apps cleans up all associated files.

#### Example: Removing an app

```bash
my-unicorn remove qownnotes
```

**Output:**

```
✅ Removed AppImage(s): /home/developer/Applications/qownnotes.AppImage
✅ Removed cache for pbek/QOwnNotes
⚠️  No backups found at: /home/developer/Applications/backups/qownnotes
✅ Removed desktop entry for qownnotes
✅ Removed icon: /home/developer/Applications/icons/qownnotes.png
✅ Removed config for qownnotes
```

## Batch Operations

Install or update multiple apps at once for efficiency.

### Example: Installing multiple apps

```bash
my-unicorn install flameshot legcord appflowy standard-notes
```

**Output:**

```
Fetching from API:
GitHub Releases      2/2 Retrieved

Downloading (2/2):
Flameshot-13.3.0.x86_64      48.4 MiB   5.1 MB/s 00:00 [==============================]   100% ✓
Legcord-1.2.1-linux-x86_64  139.5 MiB  11.0 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying flameshot ✓
(2/2) Installing flameshot ✓
(1/2) Verifying legcord ✓
(2/2) Installing legcord ✓

📦 Installation Summary:
--------------------------------------------------
legcord                   ✅ 1.2.1
flameshot                 ✅ 13.3.0
appflowy                  ℹ️  Already installed
standard-notes            ℹ️  Already installed

🎉 Successfully installed 2 app(s)
ℹ️  2 app(s) already installed
```

### Example: Updating multiple apps

```bash
my-unicorn update keepassxc flameshot legcord appflowy standard-notes
```

**Output:**

```
Fetching from API:
GitHub Releases      5/5 Retrieved from cache

Downloading (5/5):
KeePassXC-2.7.11-1-x86_64              46.9 MiB   2.5 MB/s 00:00 [==============================]   100% ✓
Flameshot-13.3.0.x86_64                48.4 MiB   2.6 MB/s 00:00 [==============================]   100% ✓
Legcord-1.2.1-linux-x86_64            139.5 MiB   5.1 MB/s 00:00 [==============================]   100% ✓
AppFlowy-0.11.1-linux-x86_64           77.6 MiB   5.2 MB/s 00:00 [==============================]   100% ✓
standard-notes-3.201.10-linux-x86_64  159.1 MiB  10.1 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying keepassxc ✓
(2/2) Installing keepassxc ✓
(1/2) Verifying flameshot ✓
(2/2) Installing flameshot ✓
(1/2) Verifying appflowy ✓
(2/2) Installing appflowy ✓
(1/2) Verifying legcord ✓
(2/2) Installing legcord ✓
(1/2) Verifying standard-notes ✓
(2/2) Installing standard-notes ✓

📦 Update Summary:
--------------------------------------------------
legcord                   ✅ 0.1.0 → 1.2.1
flameshot                 ✅ 0.1.0 → 13.3.0
appflowy                  ✅ 0.1.0 → 0.11.1
keepassxc                 ✅ 0.1.0 → 2.7.11
standard-notes            ✅ 0.1.0 → 3.201.10

🎉 Successfully updated 5 app(s)
```

### Example: Updating all installed apps

```bash
my-unicorn update
```

**Output:**

```
Fetching from API:
GitHub Releases      3/3 Retrieved from cache

Downloading (3/3):
zen-x86_64                    110.6 MiB   3.3 MB/s 00:00 [==============================]   100% ✓
tagspaces-linux-x86_64-6.9.0  149.4 MiB   8.6 MB/s 00:00 [==============================]   100% ✓
superProductivity-x86_64      129.1 MiB   5.4 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying zen-browser ✓
(2/2) Installing zen-browser ✓
(1/2) Verifying super-productivity ✓
(2/2) Installing super-productivity ✓
(1/2) Verifying tagspaces ✓
(2/2) Installing tagspaces ✓


📦 Update Summary:
--------------------------------------------------
tagspaces                 ✅ 6.8.2 → 6.9.0
super-productivity        ✅ 17.1.2 → 17.1.3
zen-browser               ✅ 1.18.4b → 1.18.5b
neovim                    ℹ️  Already up to date (0.11.6)
kdiskmark                 ℹ️  Already up to date (3.2.0)
legcord                   ℹ️  Already up to date (1.2.1)
obsidian                  ℹ️  Already up to date (1.11.7)
qownnotes                 ℹ️  Already up to date (26.2.0)
cherrytree                ℹ️  Already up to date (1.6.3)
keepassxc                 ℹ️  Already up to date (2.7.11)
heroicgameslauncher       ℹ️  Already up to date (2.19.1)
weektodo                  ℹ️  Already up to date (2.2.0)
endless-sky               ℹ️  Already up to date (0.10.16)
nuclear                   ℹ️  Already up to date (0.6.48)
flameshot                 ℹ️  Already up to date (13.3.0)
beekeeper-studio          ℹ️  Already up to date (5.5.6)
standard-notes            ℹ️  Already up to date (3.201.10)
freetube                  ℹ️  Already up to date (0.23.13-beta)
appflowy                  ℹ️  Already up to date (0.11.1)

🎉 Successfully updated 3 app(s)
ℹ️  16 app(s) already up to date
```

## Understanding the Output

### API Fetching Phase

- **Fetching...**: Contacting GitHub API
- **Retrieved**: Got release data
- **Retrieved from cache**: Using saved data to skip API call

### Downloading Phase

Shows progress bars with speed and completion status.

### Installing Phase

- **Verifying**: Checking file integrity with checksums
- **✓**: Success
- **⚠**: Warning (e.g., no checksums provided)

### Summary Phase

- **✅**: Successfully installed/updated
- **⚠️**: Warnings present
- **ℹ️**: Already installed (no action needed)
