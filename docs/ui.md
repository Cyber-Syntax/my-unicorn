# CLI Output Showcase

> [!NOTE]
> my-unicorn real output showcases the command-line interface during different operations.

> [!TIP]
> Alignment: Status line is aligned to the right according to the terminal width and appimage names are aligned to the left.
>
> Truncation: App names are truncated to fit within the terminal width.

> [!WARNING]
> App names are truncated to fit within the terminal width. (This might be changed in the future because of the cli unix design seems like don't care about the good looking, it just want to be simple and efficient, so we might be remove truncation in the future)

## Installation Examples

### With Warnings

Sometimes apps don't provide checksums for verification. Here's what that looks like:

#### Example: Installing an app without checksums

```bash
my-unicorn install weektodo
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      3/3 Retrieved
:: Retrieving appimages...
AppFlowy-0.11.1-linux-x86_64     77.6 MiB   5.3 MB/s 00:00 [==============================]   100%
QOwnNotes-x86_64                 41.6 MiB   4.5 MB/s 00:00 [==============================]   100%
WeekToDo-2.2.0                  108.6 MiB  10.7 MB/s 00:00 [==============================]   100%
Total (3/3)                     205.6 MiB   4.0 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓
(1/2) Verifying appflowy ✓
(2/2) Installing appflowy ✓
(1/2) Verifying weektodo !
    not verified (dev did not provide checksums)
(2/2) Installing weektodo ✓
:: Creating transaction summary...
appflowy                  ✓ 0.11.1
qownnotes                 ✓ 26.2.4
weektodo                  ✓ 2.2.0
                             ! Not verified - developer did not provide checksums
```

#### Example: Installing from a GitHub URL with partial verification

```bash
my-unicorn install https://github.com/Legcord/Legcord
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      1/1 Retrieved
:: Retrieving appimages...
Legcord-1.2.1-linux-x86_64          139.5 MiB  10.7 MB/s 00:00 [==============================]   100%
Total (1/1)                         139.5 MiB  10.7 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying legcord ✓
(2/2) Installing legcord ✓
:: Creating transaction summary...
legcord                   ✓ 1.2.1
                             ! Partial verification: 2 passed, 1 failed
```

### Without Warnings

When everything verifies perfectly, you get clean output.

#### Example: Fresh install from API

```bash
my-unicorn install qownnotes appflowy
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      2/2 Retrieved
:: Retrieving appimages...
AppFlowy-0.11.1-linux-x86_64          77.6 MiB  10.8 MB/s 00:00 [==============================]   100%
QOwnNotes-x86_64                      41.6 MiB   3.6 MB/s 00:00 [==============================]   100%
Total (2/2)                          118.2 MiB  10.7 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓
(1/2) Verifying appflowy ✓
(2/2) Installing appflowy ✓
:: Creating transaction summary...
appflowy                  ✓ 0.11.1
qownnotes                 ✓ 26.2.4
```

## Update Examples

Updates show version changes and use cached data when available.

#### Example: Updating an app

```bash
my-unicorn update qownnotes
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      1/1 Retrieved from cache
:: Retrieving appimages...
QOwnNotes-x86_64                    41.6 MiB   8.7 MB/s 00:00 [==============================]   100%
Total (1/1)                         41.6 MiB   8.7 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓
:: Creating transaction summary...
qownnotes                 ✓ 0.1.0 → 26.2.0
```

#### Example may still building

- This happens when the release is new and the AppImage asset hasn't finished building yet.

```bash
:: Querying upstream releases...
GitHub Releases      2/2 Retrieved from cache
:: Retrieving appimages...
QOwnNotes-x86_64                    57.8 MiB  10.0 MB/s 00:00 [==============================]   100%
Total (1/1)                         57.8 MiB  10.0 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying qownnotes ✓
(2/2) Installing qownnotes ✓
:: Creating transaction summary...
qownnotes                 ✓ 0.1.0 → 26.5.5
ytmdesktop                × Update failed
                             → AppImage not found in release - may still be building
appflowy                  Already up to date (0.11.8)
```

## Remove Examples

Removing apps cleans up all associated files.

#### Example: Removing an app

```bash
my-unicorn remove qownnotes
```

**Output:**

```
✓ Removed AppImage(s): /home/developer/Applications/qownnotes.AppImage
✓ Removed cache for pbek/QOwnNotes
! No backups found at: /home/developer/Applications/backups/qownnotes
✓ Removed desktop entry for qownnotes
✓ Removed icon: /home/developer/Applications/icons/qownnotes.png
✓ Removed config for qownnotes
```

## Batch Operations

Install or update multiple apps at once for efficiency.

### Example: Installing multiple apps

```bash
my-unicorn install flameshot legcord appflowy standard-notes
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      2/2 Retrieved
:: Retrieving appimages...
Flameshot-13.3.0.x86_64           48.4 MiB   5.1 MB/s 00:00 [==============================]   100%
Legcord-1.2.1-linux-x86_64        139.5 MiB  11.0 MB/s 00:00 [==============================]   100%
Total (2/2)                       187.9 MiB  11.0 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying flameshot ✓
(2/2) Installing flameshot ✓
(1/2) Verifying legcord ✓
(2/2) Installing legcord ✓
:: Creating transaction summary...
legcord                   ✓ 1.2.1
flameshot                 ✓ 13.3.0
appflowy                  Already installed
standard-notes            Already installed
```

### Example: Updating multiple apps

```bash
my-unicorn update keepassxc flameshot legcord appflowy standard-notes
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      5/5 Retrieved from cache
:: Retrieving appimages...
KeePassXC-2.7.11-1-x86_64              46.9 MiB   2.5 MB/s 00:00 [==============================]   100%
Flameshot-13.3.0.x86_64                48.4 MiB   2.6 MB/s 00:00 [==============================]   100%
Legcord-1.2.1-linux-x86_64            139.5 MiB   5.1 MB/s 00:00 [==============================]   100%
AppFlowy-0.11.1-linux-x86_64           77.6 MiB   5.2 MB/s 00:00 [==============================]   100%
standard-notes-3.201.10-linux-x86_64  159.1 MiB  10.1 MB/s 00:00 [==============================]   100%
Total (5/5)                           382.5 MiB  10.1 MB/s 00:00 [==============================]   100%
:: Processing package changes...
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
:: Creating transaction summary...
legcord                   ✓ 0.1.0 → 1.2.1
flameshot                 ✓ 0.1.0 → 13.3.0
appflowy                  ✓ 0.1.0 → 0.11.1
keepassxc                 ✓ 0.1.0 → 2.7.11
standard-notes            ✓ 0.1.0 → 3.201.10
```

### Example: Updating all installed apps

```bash
my-unicorn update
```

**Output:**

```
:: Querying upstream releases...
GitHub Releases      3/3 Retrieved from cache
:: Retrieving appimages...
zen-x86_64                          110.6 MiB   3.3 MB/s 00:00 [==============================]   100%
tagspaces-linux-x86_64-6.9.0        149.4 MiB   8.6 MB/s 00:00 [==============================]   100%
superProductivity-x86_64            129.1 MiB   5.4 MB/s 00:00 [==============================]   100%
Total (3/3)                         389.1 MiB   8.6 MB/s 00:00 [==============================]   100%
:: Processing package changes...
(1/2) Verifying zen-browser ✓
(2/2) Installing zen-browser ✓
(1/2) Verifying super-productivity ✓
(2/2) Installing super-productivity ✓
(1/2) Verifying tagspaces ✓
(2/2) Installing tagspaces ✓
:: Creating transaction summary...
tagspaces                 ✓ 6.8.2 → 6.9.0
super-productivity        ✓ 17.1.2 → 17.1.3
zen-browser               ✓ 1.18.4b → 1.18.5b
neovim                    Already up to date (0.11.6)
kdiskmark                 Already up to date (3.2.0)
legcord                   Already up to date (1.2.1)
obsidian                  Already up to date (1.11.7)
qownnotes                 Already up to date (26.2.0)
cherrytree                Already up to date (1.6.3)
keepassxc                 Already up to date (2.7.11)
heroicgameslauncher       Already up to date (2.19.1)
weektodo                  Already up to date (2.2.0)
endless-sky               Already up to date (0.10.16)
nuclear                   Already up to date (0.6.48)
flameshot                 Already up to date (13.3.0)
beekeeper-studio          Already up to date (5.5.6)
standard-notes            Already up to date (3.201.10)
freetube                  Already up to date (0.23.13-beta)
appflowy                  Already up to date (0.11.1)
```

### Example: already installed

```bash
my-unicorn install appflowy qownnotes
```

**Output:**

```
✓ All 2 specified app(s) are already installed:
   - appflowy
   - qownnotes
```

### Example: already updated

```bash
my-unicorn install appflowy qownnotes
```

**Output:**

```
:: Creating transaction summary...
qownnotes                 Already up to date (26.5.5)
appflowy                  Already up to date (0.11.8)
```

## Understanding the Output

### API Fetching Phase

- **Fetching...**: Contacting GitHub API
- **Retrieved**: Got release data
- **Retrieved from cache**: Using saved data to skip API call

### Downloading Phase

Shows progress bars with speed and percentage completion.

### Installing Phase

- **Verifying**: Checking file integrity with checksums
- **✓**: Success
- **!**: Warning (e.g., no checksums provided)

### Summary Phase

- **✓**: Successfully installed/updated
- **!**: Warnings present
- Already installed (no action needed)
