# Style: omgadrian (Cinematic Story)

Numbers live in `style.json`. This file holds the judgement calls. Measured from 2 reels: add more references and
re-run `scripts/analyze_style.py` to tighten pacing and grade.

## The look in one line
A short film about the speaker: cinematic shots that change every two seconds, a big yellow word that lands the beat,
and quiet serif subtitles underneath.

## Rules
- **Big title word** = the beat of the line, 1–3 words, UPPERCASE condensed yellow (Anton), ~85% of frame width, top
  third. A small italic serif lead-in sits above it ("Do you wanna make / **BETTER**", "use it / **FOREVER**").
  One every 6–12 s, never two on screen.
- **Subtitles** are small serif (Playfair), pale yellow, lower third (~78% height), full short phrases, often ending
  with "..". No keyword pops.
- **B-roll leads.** Talking head is only ~1/3 of the reel. Cut every 1.5–3 s. Prefer shots with movement (walking,
  driving, hands, a door, a city), wide → close.
- **Location changes** get a whip-pan / motion-blur transition. Hard cuts otherwise.
- **Black & white** for reflective or "before" lines (about 5–10% of the reel), then back to colour on the turn.
- **Cards:** photos, screenshots and old posts float as cards on a dark grid or light paper background, drifting slowly,
  for "since then / my journey" moments.
- **Grade:** warm and filmic: lifted blacks, warm highlights, slightly muted greens, light grain and vignette.
- **Music** carries the edit: hit the big title words on the beat; switch track at the big turn.

## Can't do in CapCut (use the fallback)
- 3D rotating thumbnail carousel → flat card slideshow.
- Video inside the letters (knockout) → big yellow title over darkened footage.
- Paper cut-out stop-motion → a photo card, or skip.

## Don't
- Their footage, music or logos. The style is the reference, not the content.
- Big title on every line.

## CapCut template: `STYLE omgadrian`
Must contain: a big title text (Anton-style, yellow) with a blur-in animation, a small italic serif lead-in text, a
serif subtitle text, the adjustment layer with this grade (incl. grain + vignette if the CapCut version has them), one
whip/motion-blur transition and one zoom-blur transition, and a B&W adjustment (saturation -100) as a second layer.
