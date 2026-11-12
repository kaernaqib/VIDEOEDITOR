# The one prompt

Install the skill once. Unzip it into `~/.claude/skills/` so that the result is `~/.claude/skills/voiceover-glass-reel/SKILL.md`.
Then open After Effects, start Claude Code in any folder, and send:

```text
Use the voiceover-glass-reel skill. Here is my voiceover: /path/to/my_voiceover.wav
Turn it into the finished reel: cut out all pauses and breaths, write the visual story from what I say, generate every picture
in Higgsfield (a host lip-synced to my voice on an old TV, the characters, the locations, the story clips, the music), and build
it in After Effects. Every generated clip goes in a floating rounded glass frame with a thin glowing border and a smooth
push-in. When I list points, put a moving perspective grid behind them and flip each keyword's colour right as I say it. The main
captions are big and spread across the frame, and the glass cards land exactly on the cut. Check it, fix what looks off, and
render the final 1080p MP4.
```

Optional additions to the same message:
- `Script: <paste the text>`: names and spelling in the captions will then match the script.
- `Make the host look like me: /path/to/my_photo.jpg`
- `Look: colour, modern tech documentary`. The default is a black-and-white 1950s archival documentary.
- `Accent colour: #FF3B30`

Claude asks twice along the way:
1. to approve the Higgsfield credit total;
2. to approve the logo downloads (only names you actually say).
Everything else runs on its own.
