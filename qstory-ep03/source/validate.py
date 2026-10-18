from pathlib import Path
import json
import re

root = Path(__file__).resolve().parent
m = json.loads((root / "EP03_timeline.json").read_text(encoding="utf-8"))
checks = []

def require(condition: bool, text: str) -> None:
    if not condition:
        raise AssertionError(text)
    checks.append("PASS: " + text)

require(m["fps"] == 30 and m["durationInFrames"] == 5400, "180 seconds at 30 fps = 5400 frames")
for group in ("scenes", "shots"):
    cursor = 0
    seen = set()
    for x in m[group]:
        require(x["id"] not in seen, group + " unique ID: " + x["id"])
        seen.add(x["id"])
        require(x["fromFrame"] == cursor, group + " no gap/overlap: " + x["id"])
        require(x["durationInFrames"] > 0, group + " positive duration: " + x["id"])
        require(x["fromFrame"] == round(x["startSec"] * m["fps"]), group + " start time agrees: " + x["id"])
        cursor += x["durationInFrames"]
        require(cursor == round(x["endSec"] * m["fps"]), group + " end time agrees: " + x["id"])
    require(cursor == m["durationInFrames"], group + " covers exactly the full film")
scenes = {s["id"]: s for s in m["scenes"]}
shots = {s["id"]: s for s in m["shots"]}
for s in m["shots"]:
    p = scenes[s["sceneId"]]
    require(p["fromFrame"] <= s["fromFrame"] and s["fromFrame"] + s["durationInFrames"] <= p["fromFrame"] + p["durationInFrames"], "shot within scene: " + s["id"])
end = 0
for c in m["captions"]:
    shot = shots[c["shotId"]]
    require(end <= c["fromFrame"] < c["toFrameExclusive"] <= 5400, "caption ordered and in range: " + c["id"])
    require(shot["fromFrame"] <= c["fromFrame"] and c["toFrameExclusive"] <= shot["fromFrame"] + shot["durationInFrames"], "caption within shot: " + c["id"])
    end = c["toFrameExclusive"]
    for cue in m["soundCues"]:
        require(c["toFrameExclusive"] <= cue["fromFrame"] or c["fromFrame"] >= cue["toFrameExclusive"], "voice does not overlap silence: " + c["id"])
for s in m["shots"]:
    text = "".join(c["text"] for c in m["captions"] if c["shotId"] == s["id"])
    require(text == s["voice"], "caption text matches narration: " + s["id"])
srt = (root / "EP03_zh_planned.srt").read_text(encoding="utf-8")
require(len(re.findall(r" --> ", srt)) == len(m["captions"]), "SRT cue count agrees with timeline")
require(m["status"] == "DESIGN_HANDOFF_NOT_RENDERED", "delivery state does not imply a rendered film")
spoken = "".join(s["voice"] for s in m["shots"])
char_count = len(re.findall(r"[\u4e00-\u9fff]", spoken))
summary = f"Validated: {len(m['scenes'])} scenes, {len(m['shots'])} shots, {len(m['captions'])} planned subtitle cues, {char_count} Chinese spoken characters.\n{len(checks)} metadata checks passed.\nNot tested: React implementation, Studio preview, media assets, recorded audio, GPU rendering or final export.\n"
(root / "validation_report.txt").write_text(summary + "\n" + "\n".join(checks) + "\n", encoding="utf-8")
print(summary)
