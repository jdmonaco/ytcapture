# ytcapture

Extract video frames and transcripts into Obsidian-compatible markdown notes.

This package provides two CLI tools:
- **ytcapture** - Process YouTube videos (with transcripts)
- **vidcapture** - Process local video files

## Why ytcapture?

Watching a lecture, tutorial, or presentation? **ytcapture** and **vidcapture** turn any video into a searchable, skimmable markdown note with:

- **Embedded frame images** at regular intervals so you can see what's on screen
- **Timestamped transcript segments** aligned to each frame
- **Obsidian-ready format** with YAML frontmatter and `![[wikilink]]` embeds
- **Smart deduplication** that removes redundant frames (great for slide-based content)
- **AI-generated titles** using Claude Haiku for concise, informative filenames (optional)

No more scrubbing through hour-long videos to find that one slide. Your notes become a visual index of the entire video.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (for frame extraction)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (for video/transcript fetching)

On macOS:
```bash
brew install ffmpeg yt-dlp
```

## Installation

```bash
# Clone the repository
git clone https://github.com/jdmonaco/ytcapture.git
cd ytcapture

# Install as a CLI tool with uv (recommended)
uv tool install -e .

# Or include AI title generation support (requires ANTHROPIC_API_KEY)
uv tool install -e ".[ai]"

# Or install with pip
pip install -e .
# pip install -e ".[ai]"  # with AI titling
```

## Usage

### ytcapture (YouTube videos)

```bash
# Basic usage - outputs to current directory
ytcapture "https://www.youtube.com/watch?v=VIDEO_ID"

# Multiple videos at once
ytcapture URL1 URL2 URL3

# Process an entire playlist (auto-expands)
ytcapture "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# On macOS, just copy a YouTube URL (or playlist) and run without arguments
ytcapture

# Skip confirmation for large playlists (>10 videos)
ytcapture "https://www.youtube.com/playlist?list=PLAYLIST_ID" -y

# Specify output directory (relative to cwd or absolute path)
ytcapture URL -o my-notes/

# Adjust frame interval (default: 15 seconds)
ytcapture URL --interval 30

# Extract more frames with aggressive deduplication
ytcapture URL --interval 5 --dedup-threshold 0.80
```

### vidcapture (local video files)

```bash
# Basic usage
vidcapture meeting.mp4

# Multiple files
vidcapture video1.mp4 video2.mkv -o notes/

# Full-decode mode for accurate timestamps (fast keyframe seeking is the default)
vidcapture long-workshop.mp4 --no-fast --interval 60

# JSON output for scripting
vidcapture video.mp4 --json
```

## Output Structure

```
./
├── images/
│   └── VIDEO_ID/
│       ├── frame-0000.jpg
│       ├── frame-0001.jpg
│       └── ...
├── transcripts/
│   └── raw-transcript-VIDEO_ID.json
└── Video Title (Channel Name) 20241120.md
```

Assets are organized by video ID to support multiple video captures in the same directory.

## Example Output

The generated markdown looks like this:

```markdown
---
title: Understanding Neural Networks
source: https://www.youtube.com/watch?v=abc123
author:
  - Deep Learning Channel
created: '2024-12-15'
published: '2024-11-20'
description: An introduction to neural networks and deep learning fundamentals...
tags:
  - youtube
---

# Understanding Neural Networks

> An introduction to neural networks and deep learning fundamentals.

## 00:00:00

![[images/abc123/frame-0000.jpg]]

Welcome to this tutorial on neural networks. Today we'll cover the basics.

## 00:00:15

![[images/abc123/frame-0001.jpg]]

Let's start by understanding what a neuron is and how it processes information.
```

## Configuration

Both tools use a shared config file at `~/.ytcapture.yml` (auto-created on first run):

```yaml
# Frame extraction defaults
interval: 15           # Seconds between frames
frame_format: jpg      # jpg or png
dedup_threshold: 0.85  # 0.0-1.0, higher = more aggressive

# ytcapture-specific
language: en
prefer_manual: false
keep_video: false
ai_title: true         # Use Claude Haiku to generate concise titles

# vidcapture-specific
fast: true             # Use fast keyframe seeking (--no-fast for full decode)
```

CLI options override config values. The `--help` output shows your current defaults from config.

## Shell Completion

Bash completion is available for both commands:

```bash
# Install completions
ytcapture completion bash --install
vidcapture completion bash --install

# Restart your shell or source your bashrc
source ~/.bashrc
```

Tab completion for `-o/--output` completes directories relative to the current directory.

## Options

### ytcapture options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | cwd | Output directory (relative to cwd or absolute) |
| `--interval` | 15 | Frame extraction interval in seconds |
| `--max-frames` | None | Maximum number of frames to extract |
| `--frame-format` | jpg | Frame format: `jpg` or `png` |
| `--language` | en | Transcript language code |
| `--dedup-threshold` | 0.85 | Similarity threshold for removing duplicate frames (0.0-1.0) |
| `--no-dedup` | - | Disable frame deduplication |
| `--prefer-manual` | - | Only use manual transcripts |
| `--keep-video` | - | Keep downloaded video file after frame extraction |
| `--no-ai-title` | - | Disable AI title generation (see below) |
| `-y, --yes` | - | Skip confirmation prompt for large batches (>10 videos) |
| `-v, --verbose` | - | Verbose output |

### vidcapture options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | cwd | Output directory (relative to cwd or absolute) |
| `--interval` | 15 | Frame extraction interval in seconds |
| `--max-frames` | None | Maximum number of frames to extract |
| `--frame-format` | jpg | Frame format: `jpg` or `png` |
| `--dedup-threshold` | 0.85 | Similarity threshold for removing duplicate frames (0.0-1.0) |
| `--no-dedup` | - | Disable frame deduplication |
| `--fast / --no-fast` | True | Fast keyframe seeking (use `--no-fast` for full decode) |
| `--json` | - | Output JSON instead of console output (for scripting) |
| `-f, --force` | - | Overwrite existing output files without prompting |
| `-v, --verbose` | - | Verbose output |

## AI Title Generation

YouTube titles are often long and SEO-stuffed. When enabled, ytcapture uses Claude Haiku to generate concise titles in `{Key Person} - {Descriptive Topic}` format (e.g., "Ilya Sutskever - Scaling Neural Networks").

**Requirements:**
- Install the `ai` extra: `uv pip install "ytcapture[ai]"` or `pip install anthropic`
- Set `ANTHROPIC_API_KEY` in your environment

When both are present, AI titling is used automatically. The original YouTube title is preserved in the `original_title` frontmatter field. To disable, use `--no-ai-title` or set `ai_title: false` in config. When the API key or SDK is missing, ytcapture falls back silently to the default truncated title.

## Tips

### For slide-based presentations

Use a shorter interval with deduplication to catch slide transitions:
```bash
ytcapture URL --interval 5 --dedup-threshold 0.90
```

### For fast-moving content

Disable deduplication to keep all frames:
```bash
ytcapture URL --interval 10 --no-dedup
```

### For long videos

Limit the number of frames to avoid huge output:
```bash
ytcapture URL --max-frames 50
```

## Markdown Formatting

If you have [mdformat](https://github.com/executablebooks/mdformat) installed, ytcapture will automatically format the output markdown:

```bash
pip install mdformat mdformat-gfm mdformat-frontmatter
```

## License

MIT
