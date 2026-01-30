# ytcapture - Video Frame & Transcript Extractor

## Project Overview

This package provides two CLI tools for extracting video frames into Obsidian-compatible markdown notes:

- **ytcapture**: Extract frames and transcripts from YouTube videos
- **vidcapture**: Extract frames from local video files

Both tools share the same configuration file and frame extraction options.

## Core Functionality

### ytcapture (YouTube videos)

Given a YouTube URL, the tool:
1. Downloads the best available transcript (manual preferred, auto-generated fallback)
2. Extracts video frames at specified intervals
3. Generates an Obsidian-flavored markdown file with:
   - YAML frontmatter (title, source, author, dates, tags)
   - Timestamped transcript segments
   - Embedded frame images using `![[relative/path.jpg]]` syntax
4. Organizes output in a structured directory

### vidcapture (local videos)

Given local video file paths, the tool:
1. Extracts video metadata using ffprobe
2. Extracts video frames at specified intervals (with optional fast keyframe-seeking mode)
3. Generates an Obsidian-flavored markdown file with:
   - YAML frontmatter (title, created date, tags)
   - Embedded frame images
4. Handles filename collisions with automatic suffixes

## Output Structure

```
<Sanitized Video Title>/
├── images/                          # or frames/
│   ├── frame-0001.jpg
│   ├── frame-0002.jpg
│   └── ...
├── transcript/
│   └── raw-transcript.json          # Raw transcript data
└── <Sanitized Video Title> YYYYMMDD.md
```

## Markdown Output Format

### YAML Frontmatter
```yaml
---
title: <Video Title>
source: <YouTube URL>
author:
  - <Channel Name>
created: YYYY-MM-DD
published: YYYY-MM-DD
description: <Video Description (truncated if long)>
tags:
  - youtube
---
```

### Body Structure
- Each transcript segment includes:
  - Timestamp heading (HH:MM:SS format)
  - Embedded frame image (closest frame before/at timestamp)
  - Transcript text
- Segments separated by blank lines for Obsidian readability

### Example Output
```markdown
---
title: Understanding Neural Networks
source: https://www.youtube.com/watch?v=abc123
author:
  - DeepLearning Channel
created: 2025-01-15
published: 2024-12-20
description: An introduction to neural networks and deep learning
tags:
  - youtube
---

## 00:00:00

![[images/frame-0001.jpg]]

Welcome to this tutorial on neural networks.

## 00:00:45

![[images/frame-0002.jpg]]

Let's start by understanding the basic architecture.
```

## CLI Interface

### ytcapture (YouTube)

```bash
# Basic usage - outputs to current directory
ytcapture "https://youtube.com/watch?v=..."

# Multiple videos or playlists
ytcapture URL1 URL2 "https://youtube.com/playlist?list=..."

# On macOS, reads URL from clipboard if no arguments
ytcapture

# Specify output directory (relative to cwd or absolute)
ytcapture URL -o captures/

# Frame extraction options
ytcapture URL --interval 30           # Frame every 30 seconds
ytcapture URL --max-frames 50         # Limit total frames
ytcapture URL --frame-format png      # PNG instead of JPG

# Transcript options
ytcapture URL --language en           # Specific language
ytcapture URL --prefer-manual         # Manual only (fail if unavailable)

# Keep downloaded video file
ytcapture URL --keep-video
```

### vidcapture (local files)

```bash
# Basic usage
vidcapture meeting.mp4

# Multiple files
vidcapture video1.mp4 video2.mkv -o notes/

# Fast mode for long videos (uses keyframe seeking)
vidcapture long-workshop.mp4 --fast --interval 60

# JSON output for scripting
vidcapture video.mp4 --json
```

## Configuration

Both tools use a shared config file at `~/.ytcapture.yml` (auto-created on first run).

```yaml
# Vault root directory (~ expanded, used for path display shortening)
vault: ~/Documents/Obsidian/Notes

# Default output directory (relative to cwd or absolute)
output: VideoCaptures

# Frame extraction defaults
interval: 15           # Seconds between frames
frame_format: jpg      # jpg or png
dedup_threshold: 0.85  # 0.0-1.0

# ytcapture-specific
language: en
prefer_manual: false
keep_video: false

# vidcapture-specific
fast: false
```

CLI options override config values. Help text shows current defaults from config.

## Shell Completion

Bash completion is available for both commands:

```bash
# Install completions (creates symlinks)
ytcapture completion bash --install
vidcapture completion bash --install

# Or output script to stdout
ytcapture completion bash > ~/.local/share/bash-completion/completions/ytcapture
```

Completion for `-o/--output` completes directories relative to cwd.

## Technical Requirements

### Dependencies
- **yt-dlp**: Video metadata and download
- **youtube-transcript-api**: Transcript extraction
- **ffmpeg-python**: Frame extraction via ffmpeg
- **click**: CLI interface
- **python-dateutil**: Date parsing
- **pyyaml**: YAML frontmatter generation

### External Requirements
- ffmpeg (system installation)
- yt-dlp (system installation)

### Python Version
- Python 3.10+

## Key Implementation Details

### Title Sanitization
- Remove invalid filename characters: `< > : " / \ | ? *`
- Replace with spaces or hyphens
- Title-case the result
- Truncate if too long (e.g., 100 chars max)

### Frame-Transcript Alignment
- Extract frames at specified intervals (default: 30 seconds)
- For each transcript segment, find the closest frame at or before its timestamp
- Embed that frame image in the markdown

### Transcript Handling
- Prefer manual transcripts over auto-generated
- If no transcripts available, create markdown with only frame embeds
- Save raw transcript JSON for reference/debugging

### Error Handling
- Video unavailable or private: Clear error message
- No transcripts available: Proceed with frames only
- ffmpeg not found: Installation instructions
- Network errors: Retry logic with exponential backoff

## Architecture

### Module Structure

- `cli.py` - Click-based CLI for both ytcapture and vidcapture entry points
- `config.py` - Configuration file handling (load, merge, path resolution)
- `video.py` - YouTube video metadata and download (yt-dlp)
- `local.py` - Local video metadata extraction (ffprobe)
- `transcript.py` - YouTube transcript fetching
- `frames.py` - Frame extraction (ffmpeg, with deduplication)
- `markdown.py` - Markdown file generation
- `metadata.py` - VideoMetadataProtocol for polymorphic metadata handling
- `completion.py` - Bash completion script handling
- `utils.py` - URL validation and utility functions

### Key Design Patterns

- **Protocol-based abstraction**: `VideoMetadataProtocol` allows both YouTube and local video metadata to work with the same markdown generation code
- **Module-level config loading**: Config is loaded once at import time for dynamic CLI defaults
- **Path display**: Uses `shorten_path()` for consistent display ($HOME → ~, OneDrive → ~/OneDrive)

## Testing Strategy

### Unit Tests
- Title sanitization edge cases
- Timestamp formatting
- Frame-transcript alignment logic
- YAML frontmatter generation

### Integration Tests
- Full pipeline with sample video
- Error cases (no transcript, unavailable video)
- Different frame extraction modes

### Manual Testing
- Various YouTube video types
- Different languages
- Videos with/without transcripts
- Edge cases (very long/short videos)

## Implementation Status

Completed features:
- ✅ Extract frames and transcripts from YouTube videos
- ✅ Extract frames from local video files
- ✅ Generate valid Obsidian-compatible markdown with embeds
- ✅ Handle missing transcripts gracefully
- ✅ Smart frame deduplication
- ✅ Fast keyframe-seeking mode for long videos
- ✅ Global configuration file with vault support
- ✅ Cwd-relative path handling for -o/--output
- ✅ Bash completion with standard directory completion
- ✅ JSON output mode for vidcapture
- ✅ Multiple video/playlist processing

## Future Considerations

- Transcript support for local videos (e.g., Whisper integration)
- Support for other video platforms (Vimeo, etc.)
- Scene detection for smarter frame selection
- Custom markdown templates
- Thumbnail generation (contact sheet)
## Claude Code Configuration

This project uses the global `~/.claude/settings.json` for all permissions and settings.

### Tools Manager: tlmgr

The `tlmgr` command manages all tool repositories from the umbrella ~/tools directory:

```bash
tlmgr --json summary  # Overall status of all 14 repos
tlmgr --json list     # Detailed status with branches
tlmgr changes         # Show uncommitted changes
tlmgr unpushed        # Show unpushed commits
```

Always use `tlmgr` (not relative paths like `./bin/tools-manager.sh`).

### Development Workflow

**Auto-allowed git operations:**
- Read: status, diff, log, show, branch, grep, blame
- Write: add, commit, push, pull, checkout, switch, restore, stash

**Require confirmation:**
- Destructive: merge, rebase, reset, cherry-pick, revert
- Force operations: push --force
- Repository changes: clone, init, submodule

### Available Development Tools

**Python:** pytest, pip, poetry, uv (install, run, sync)  
**Node:** npm (test, run, install), node  
**Build:** make, bash scripts in ./scripts/  
**Utilities:** find, grep, rg, cat, ls, tree, jq, yq, head, tail, wc  
**Documents:** pandoc, md2docx, mdformat

### Configuration

All permissions are centralized in `~/.claude/settings.json`:
- Sandbox is disabled globally
- Full read/write access to ~/tools/** and ~/agents/**
- Standard security protections (no ~/.ssh, .env files, etc.)
- Consistent behavior across all projects

No project-specific `.claude/` folders are needed.