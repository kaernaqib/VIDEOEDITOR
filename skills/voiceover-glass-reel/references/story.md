# story.json: the edit, written against the word indices

`reel.py words <proj>` prints every spoken word with its index, for example `24:ChatGPT`. A shot starts at a word index. The cut
lands one frame before that word, and the shot runs until the next shot starts. All paths are relative to `<proj>`.

```json
{
 "title": "EXPERIMENT",
 "music": "assets/music.mp3",
 "music_db": -17,
 "accent": "#FFD23F",
 "spell": {"28": "Grok", "126": "Grok"},
 "list": {"from": 61, "to": 74, "flip": [62, 69, 71]},
 "keys": [6, 15, 40, 43, 104, 113],
 "shots": [
  {"at": 0,   "kind": "type",  "text": "WHAT IF I TOLD YOU..."},
  {"at": 5,   "kind": "host",  "mode": "tv"},
  {"at": 14,  "kind": "clip",  "file": "assets/clips/c01_lying.mp4", "in": 0.5, "hit": "invert"},
  {"at": 24,  "kind": "cards", "line": "when you take", "items": [
     {"at": 24, "file": "assets/clips/c02_portraits.mp4", "in": 0.4, "logo": "assets/logos/chatgpt.png", "name": "ChatGPT"},
     {"at": 25, "file": "assets/clips/c02_portraits.mp4", "in": 2.4, "logo": "assets/logos/claude.png",  "name": "Claude"}]},
  {"at": 57,  "kind": "giant", "word": "CHOICE", "label": "one brutal", "label_at": 58},
  {"at": 61,  "kind": "clip",  "file": "assets/clips/c05_choice.mp4", "in": 0.0},
  {"at": 199, "kind": "giant", "word": "DRIFT", "label": "Emergence calls it", "label_at": 199, "sub": "normative", "sub_at": 203},
  {"at": 226, "kind": "clip",  "file": "assets/clips/c14_finale.mp4", "in": 0.0, "color": true}
 ]
}
```

## Fields
| field | meaning |
|---|---|
| `title`, `aep` | Comp comment and project file name (default `reel.aep`). |
| `music`, `music_db` | The music bed and its level. Default −17 dB under the voice; −14 is louder, −20 quieter. |
| `accent` | Keyword colour (default warm yellow `#FFD23F`). `glow` = glass border colour (default `#CFF3FF`). |
| `spell` | Caption text fixes for misheard names: `{"word index": "Correct"}`. Never change real words. |
| `list` | A spoken list of points. The grid runs from word `from` to the end of word `to`. `flip` = the keyword indices that flip colour. |
| `keys` | Caption words shown bigger and bold, with a 3-flicker entrance. At most one per sentence. |
| `shots[].at` | Word index where the shot starts. The first shot must be `0`. Indices must rise. |
| `shots[].kind` | `host`, `clip`, `type`, `giant` or `cards` (see below). |
| `shots[].hit` | Optional cut effect: `invert` (negative flick), `strobe` (white/black strobe into the cut) or `burn` (2 blown-out frames). |
| `shots[].flash` | Bleach-in flash on the first 4 frames. Default on for `clip` and `cards`. Set `false` to switch it off. |

### Kinds
- **host**, `mode: "tv"` (default) or `"full"`. The lip-synced host. `reel.py chunks` names the clip `assets/host/host_NN.mp4` in
  host order, so leave `file` out. Keep each host shot at 14 s or less.
  - `tv`: the host plays inside the green screen of `assets/tv_plate.png` (keyed), with a slow push-in.
  - `full`: full frame.
- **clip**, `file` and `in` (the source second at the shot start), plus `color: true` to keep colour. Every clip sits in the floating
  glass frame with its own blurred light behind it. Inside the `list` range, the moving grid sits behind it instead.
  - Clips that follow each other share the frame: only the first one "lands" (95→100 % in 6 frames).
- **type**, `text` (use `\n` for line breaks, at most ~24 characters a line). A black page; the text types on letter by letter.
- **giant**: `word` (1 word, shown in caps), plus optional `label` (red box, from word `label_at`) and `sub` (serif italic, from word `sub_at`).
  A dark grid page that drifts sideways.
- **cards**: `line` (a small line in the middle) and up to 4 `items`. Each item has `at` (the word where it snaps in), `file` (a clip or image),
  `in`, `logo` (a PNG for the round badge) and `name` (a big serif name in the middle until the next card).

## Rules that make it read as human-edited
- Cut on meaning, not on a timer. Shot lengths vary: 1.2–3.5 s, with host shots longer.
- Let consecutive sentences reuse **one** generated clip at different `in` times. A 10 s clip with 5 sub-shots feeds 3–5 shots,
  each showing a different sub-shot. Never show the same second twice.
- Show what is said. A number becomes a counter-like page (`type`) or a clip of that thing. A name becomes a card with its
  logo, but only when that name is spoken.
- Keep the host for the hook, the turns and the call to action. Never use two host shots in a row: put a clip between them.
- Captions are hidden on `type`, `giant` and `cards` pages, because those carry their own text. Elsewhere they show every spoken word,
  in phrases of up to 4 words.
