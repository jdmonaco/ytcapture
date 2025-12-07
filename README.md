# ytcapture

Extract video frames and transcripts from YouTube videos into Obsidian-compatible markdown notes.

## Why ytcapture?

Watching a lecture, tutorial, or presentation on YouTube? **ytcapture** turns any video into a searchable, skimmable markdown note with:

- **Embedded frame images** at regular intervals so you can see what's on screen
- **Timestamped transcript segments** aligned to each frame
- **Obsidian-ready format** with YAML frontmatter and `![[wikilink]]` embeds
- **Smart deduplication** that removes redundant frames (great for slide-based content)

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

# Or install with pip
pip install -e .
```

## Usage

```bash
# Basic usage - creates a folder with the video title
ytcapture "https://www.youtube.com/watch?v=VIDEO_ID"

# On macOS, just copy a YouTube URL and run without arguments
ytcapture

# Specify output directory
ytcapture URL -o my-notes/

# Adjust frame interval (default: 15 seconds)
ytcapture URL --interval 30

# Extract more frames with aggressive deduplication
ytcapture URL --interval 5 --dedup-threshold 0.80
```

## Output Structure

```
Video Title/
├── images/
│   ├── frame-0000.jpg
│   ├── frame-0001.jpg
│   └── ...
├── transcript/
│   └── raw-transcript.json
└── Video Title 20241215.md
```

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

![[images/frame-0000.jpg]]

Welcome to this tutorial on neural networks. Today we'll cover the basics.

## 00:00:15

![[images/frame-0001.jpg]]

Let's start by understanding what a neuron is and how it processes information.
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | Video title | Output directory |
| `--interval` | 15 | Frame extraction interval in seconds |
| `--max-frames` | None | Maximum number of frames to extract |
| `--frame-format` | jpg | Frame format: `jpg` or `png` |
| `--language` | en | Transcript language code |
| `--dedup-threshold` | 0.85 | Similarity threshold for removing duplicate frames (0.0-1.0) |
| `--no-dedup` | - | Disable frame deduplication |
| `--prefer-manual` | - | Only use manual transcripts |
| `--keep-video` | - | Keep downloaded video file after frame extraction |
| `-v, --verbose` | - | Verbose output |
| `-h, --help` | - | Show help message |

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
