# Icon Template Examples

This document shows how to use the new icon template system in catalog configuration files.

## Overview

Instead of providing full GitHub raw URLs for icons, you can now just specify the path within the repository. The system will automatically:

1. Detect the repository's default branch (main/master)
2. Build the complete GitHub raw URL
3. Generate appropriate icon filenames

## Template Format

```json
{
    "icon": {
        "url": "path/to/icon/file.png",
        "name": "appname.png"
    }
}
```

The system converts `path/to/icon/file.png` to:
`https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/path/to/icon/file.png`

## Examples

### Example 1: Nuclear Music Player

```json
{
    "nuclear": {
        "owner": "nukeop",
        "repo": "nuclear",
        "icon": {
            "url": "packages/app/resources/media/icon_512x512x32.png",
            "name": "nuclear.png"
        }
    }
}
```

**Result**: `https://raw.githubusercontent.com/nukeop/nuclear/master/packages/app/resources/media/icon_512x512x32.png`

### Example 2: AppFlowy

```json
{
    "appflowy": {
        "owner": "AppFlowy-IO",
        "repo": "AppFlowy",
        "icon": {
            "url": "frontend/resources/flowy_icons/40x/app_logo.svg",
            "name": "appflowy.svg"
        }
    }
}
```

**Result**: `https://raw.githubusercontent.com/AppFlowy-IO/AppFlowy/main/frontend/resources/flowy_icons/40x/app_logo.svg`

## Features

### Automatic Branch Detection

- System automatically detects if repo uses `main`, `master`, or other default branch
- No need to specify branch in the template path

### Path Cleaning

- Leading slashes are automatically removed
- `"/assets/icon.png"` becomes `"assets/icon.png"`

### Extension Handling

- Icon filename automatically uses app name with original extension
- `packages/icons/app.svg` → `appname.svg`
- If no extension detected, defaults to `.png`

### Fallback Support

- If template building fails, falls back to treating URL as complete URL
- Graceful error handling with detailed logging

## Migration from Full URLs

### Before (Old Format)

```json
{
    "icon": {
        "url": "https://raw.githubusercontent.com/nukeop/nuclear/master/packages/app/resources/media/icon_512x512x32.png",
        "name": "nuclear.png"
    }
}
```

### After (New Template Format)

```json
{
    "icon": {
        "url": "packages/app/resources/media/icon_512x512x32.png",
        "name": "nuclear.png"
    }
}
```

## Benefits

1. **Easier Configuration**: No need to construct full GitHub raw URLs
2. **Branch Agnostic**: Automatically works with main/master branches
3. **Less Error-Prone**: Shorter paths reduce typos
4. **Future-Proof**: Adapts if repository changes default branch
5. **Backward Compatible**: Still supports full URLs if needed

## Finding Icon Paths

To find the icon path for an app:

1. Go to the GitHub repository
2. Navigate to the icon file in the web interface
3. Copy the path from the repository root
4. Use that path in the `url` field

Example: If the file is at `https://github.com/nukeop/nuclear/blob/master/packages/app/resources/media/icon_512x512x32.png`,
use `packages/app/resources/media/icon_512x512x32.png`

## Update Behavior

When an app is updated:

- If icon was previously unavailable but now has a template path, it will be downloaded
- Desktop entries are automatically regenerated when icons change
- Icon templates are re-evaluated to handle branch changes
