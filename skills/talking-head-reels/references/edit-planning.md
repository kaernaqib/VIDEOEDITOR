# Planning the edit - from a talk to beats

The scripts handle the mechanics. What makes the reel work is the plan: which words become big
type, which sentences get footage, where the speaker's face is the best picture. Plan on the
program timeline (`analysis/program_words.json`), after the pauses are cut.

## 1. Read the talk as a story

Mark four parts:
- **Hook** (first 2-6 s): the promise or the provocation. It decides whether people keep watching.
- **Setup**: who/what/where, the rules of the situation.
- **Escalation**: the surprising turns - each turn deserves its own visual idea.
- **Payoff + call to action** (last 3-6 s): the conclusion and the ask.

## 2. Split into beats

A beat is one thought, usually 1.5-4 s, ending at a natural pause or a full stop. For every beat
decide one primary visual:

| the words are about... | show |
|---|---|
| the speaker's opinion, emotion, a question to the viewer | presenter (wide/tight) + big word in front or a subtitle |
| a concrete thing, place, event, character | B-roll insert (`full`) |
| something the viewer should see while the speaker reacts | `split` (footage top, presenter bottom) |
| a number, a rule, a mechanic, a resource | UI insert: `number`, `bar`, `cards`, `counter` text |
| brands, products, AI models, companies | `logo_flash`, `cards`, `converge`, or a logo over footage |
| a list ("first... second... third") | counters side by side (`no. 1  no. 2  no. 3`) |
| two opposing actions ("punching... robbing") | `vsplit` - first clip full, second slides into the bottom half |
| a contrast between two words | `band` - one word above the strip, one below |

Alternate: never two identical treatments in a row if the third beat can be different.

## 3. Choose the words

- **Big word (Anton)**: the single most loaded word of the beat - a verb, a number, a twist
  ("LYING", "15", "CHAOS", "LIED", "DRIFT"). One per beat, rarely two.
- **Serif accent (Didot Bold)**: the softer, ironic or elegant half ("I told you", "same town",
  "brutal", "copying"). Pairs well with an Anton word: serif above or below, both in the centre stack.
- **Subtitles (`sub`, words as spoken)**: the connective tissue between big words - short chunks
  of 2-4 words, 80-100 px, in the centre stack just under the big word (or alone where the big word
  would be). Not every sentence needs them; when a big word already says it, skip the subtitle.
- **Lead-in labels (`sub`, pop)**: a few words just above the big word ("you use", "the exact",
  "Emergence calls it").

Text should be quoted from the speech, not paraphrased. The viewer reads what they hear.

## 4. Pick footage per beat

Write the footage idea in one line: subject, action, mood, colour or B&W. Prefer concrete,
specific images that a viewer recognises instantly, with motion inside the shot. Then source it
(`broll-sourcing.md`). If nothing fits, stay on the presenter with a big word - that is better
than a generic clip.

## 5. Presenter framing plan

`zoom` in the EDL: a list of `[t0, t1, "wide"|"tight"]`. Switch at cuts (hides the jump) and on
emphasis. Hook and CTA usually tight. If you leave `zoom` out, the planner alternates at every cut.

## 6. Worked example (first 25 s of a real reel about an AI experiment)

| t (s) | words | on screen | text (font size, y) |
|---|---|---|---|
| 0.00-0.84 | "What if I told you" | presenter tight | `WHAT IF` (Anton 200, y 1122) + `I told you` (serif 150, y 1300) |
| 0.84-1.86 | "the safest AI" | `logo_flash`: 4 model logos on black/red, silhouette flash | `the safest` (Didot 120, y 1028) + `AI` (Anton 200, y 1203) |
| 1.86-3.16 | "you use every day" | `full`, colour shot: a phone in a shirt pocket | `you use` (label 100, y 847) + `EVERY DAY` (Anton 170, y 977) |
| 3.16-6.10 | "is actually lying to you?" | `frame` on red, split layout: three machine-eye close-ups, match cut | `LYING` (Anton 170, y 870) + `to you` (serif 150, on the seam) |
| 6.10-9.60 | "researchers took the four biggest models..." | `cards` (4 model cards, x10 agents) in split | subtitle on the seam (100, y ~960) |
| 9.60-12.32 | "...a 15-day survival test" | `full` in split: two clips stacked | `15` (Anton 224 red, y 843) + `DAY SURVIVAL TEST` (label 70, y 1010) |
| 12.32-14.70 | "things get weird very fast" | `full`: coloured characters on B&W | `WEIRD` (Anton 200 red, y 960) + `very fast.` (subtitle 100, y 1095) |
| 14.70-16.72 | "the exact same town" | `full`, colour | `the exact` (label 100) + `same town` (serif 150) |
| 16.72-19.20 | "same jobs and one brutal choice" | `full` | `brutal` (serif 150, y 828) + `CHOICE` (Anton 200 red, y 1008) |
| 19.20-20.74 | "work together to stay alive" | `band` in split | `WORK` (Anton 163, y 805) + `TOGETHER` (Anton 120 red, y 1063) |
| 20.74-23.36 | "or break the law to survive on your own" | `full` in split, colour street riot | `or` + `BREAK THE LAW` (Anton 109 red, on the seam) |

Ending of the same reel: presenter wide/tight, `If you want\nto watch` (label, two lines) +
`the full experiment\nyourself,` (serif, two lines) under the neck, then `COMMENT\n'TOWN'` (Anton
140 white, two lines) - CTA always in front of the presenter, never over B-roll.

## 7. Show the plan

Give the user the beat table (time, words, visual, text, footage idea) and wait for a go before
sourcing or generating footage. Adjust freely at this stage.
