# VIDEOEDITOR

Claude skills untuk edit video (Reels / TikTok / Shorts).

| Skill | Guna untuk |
|---|---|
| `skills/reel-editor` | Edit Reel 9:16 dalam projek CapCut sendiri (format education, vlog, do & don't, before/after). Bergantung pada `capcut-talking-head-edit`. |
| `skills/capcut-talking-head-edit` | Edit video talking-head dalam CapCut dengan tulis fail timeline terus, tambah motion graphics. |
| `skills/talking-head-reels` | Render Reel talking-head terus guna Python + ffmpeg (tanpa app edit). |
| `skills/voiceover-glass-reel` | Tukar voiceover jadi reel dokumentari 16:9 dalam After Effects. |

## Pasang

Salin folder skill yang kau nak ke `~/.claude/skills/` (atau `.claude/skills/` dalam projek), contohnya:

```bash
cp -r skills/reel-editor skills/capcut-talking-head-edit ~/.claude/skills/
```

API key (Pixabay, Pexels) jangan simpan dalam repo ni. Set sebagai environment variable (`PIXABAY_API_KEY`, `PEXELS_API_KEY`).
