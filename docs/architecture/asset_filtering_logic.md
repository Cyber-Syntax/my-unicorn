These are tested on tests/test_asset_filtering.py

### Assets to KEEP (Must Not Be Filtered)

These should pass through filtering and be cached:

```
# checksum files
✅ "QOwnNotes-x86_64.AppImage.sha256sum"
✅ "Flameshot-13.3.0.x86_64.AppImage.sha256sum"
✅ "<appimage_name>.sha512sum"
✅ "KeePassXC-2.7.10-x86_64.AppImage.DIGEST"
✅ "latest-linux.yml"
✅ "SHA256SUMS"
✅ "SHA256SUMS.txt"

# appimages
✅ "QOwnNotes-x86_64.AppImage"
✅ "standard-notes-3.198.5-linux-x86_64.AppImage"
✅ "zen-x86_64.AppImage"
✅ "tagspaces-linux-x86_64-6.6.4.AppImage"
✅ "Obsidian-1.9.14.AppImage"
✅ "nuclear-v0.6.48-x86_64.AppImage"
✅ "nvim-linux-x86_64.appimage"
✅ "WeekToDo-2.2.0.AppImage"
✅ "Joplin-3.4.12.AppImage"
✅ "Joplin-3.4.12.AppImage.sha512"
✅ "superProductivity-x86_64.AppImage"
✅ "KeePassXC-2.7.10-x86_64.AppImage"
✅ "CherryTree-1.6.2-x86_64.AppImage"
✅ "Flameshot-13.3.0.x86_64.AppImage"
✅ "Endless_Sky-v0.10.16-x86_64.AppImage"
✅ "Beekeeper-Studio-5.4.9.AppImage"
✅ "Zettlr-3.6.0-x86_64.AppImage"
✅ "Legcord-1.1.5-linux-x86_64.AppImage"
✅ "KDiskMark-3.2.0-fio-3.40-x86_64.AppImage"
✅ "Heroic-2.18.1-linux-x86_64.AppImage"
✅ "AppFlowy-0.10.2-linux-x86_64.AppImage"
✅ "freetube-0.23.12-beta-amd64.AppImage"  ⭐ Special case: this app is beta all the time
```

### Assets to EXCLUDE (Must Be Filtered Out)

These should NOT appear in cache files:

```
❌ "freetube-0.23.12-beta-armv7l.AppImage"           # ARM 32-bit
❌ "freetube-0.23.12-beta-arm64.AppImage"            # ARM 64-bit
❌ "QOwnNotes-x86_64-Qt6-experimental.AppImage"      # Experimental
❌ "QOwnNotes-x86_64-Qt6-experimental.AppImage.sha256sum"  # Experimental checksum
❌ "Obsidian-1.9.14-arm64.AppImage"                  # ARM 64-bit
❌ "nvim-linux-arm64.appimage"                       # ARM 64-bit
❌ "latest-mac-arm64.yml"                            # macOS
❌ "KeePassXC-2.7.10-Win64.zip.DIGEST"               # Windows
❌ "KeePassXC-2.7.10-Win64.msi.DIGEST"               # Windows
❌ "KeePassXC-2.7.10-Win64-LegacyWindows.zip.DIGEST" # Windows
❌ "KeePassXC-2.7.10-Win64-LegacyWindows.msi.DIGEST" # Windows
❌ "KeePassXC-2.7.10-arm64.dmg.DIGEST"               # macOS
❌ "KeePassXC-2.7.10-x86_64.dmg.DIGEST"              # macOS
```
