# EP05 v03 procedural music notes

Status: PCM mix rendered locally; master measured −17.0 LUFS / −1.8 dBTP, 48 kHz stereo, exactly5,760,000 samples/channel. The score and master are exact zero during frames5400–5424. No new narration/provider calls. Human listening remains pending.

The score is a deterministic, locally synthesized ambient bed. It uses slow additive tones, gently moving stereo levels, and rounded envelopes rather than a sub-bass-only drone or sharp percussion.

| Time | Musical material | Intended feel |
| --- | --- | --- |
| 0–60 s | Am(add9) → Fmaj7 → Dm(add9) → Esus, with each harmonic field held about 15 s and neighboring chords crossfaded over 10 s | Warm, curious opening that gradually gains unresolved tension |
| 60–90 s | A low-string harmonic bed with a soft 3.6 s pulse and sparse, smoothly enveloped 220–880 Hz notes | More pressing and dense without a hard percussion hit |
| Frames 5400–5424 | Exact digital silence in the score and final master | A complete vacuum interval |
| Frame 5425–115.5 s | An airy suspended Cmaj7/Fmaj7 pad with sparse soft bells, fading in after the vacuum | Cold, spacious release |
| 115.5–120 s | Smooth amplitude tail to silence | Quiet close |

The chord voices include fundamentals from bass support through the midrange, with particular weight around 220–880 Hz so the score remains audible on small speakers. Bell overtones are omitted above 1.2 kHz; the score has no fundamentals above 880 Hz. Narration uses measured PCM-active bounds for a −6 dB target duck, with a 60 ms attack and 420 ms release. This leaves room for speech in the 1–4 kHz band while allowing the music to remain present beneath it.

All audio is synthesized by the project’s own deterministic oscillator and envelope code. No recordings, sample libraries, external music, provider calls, or network resources are used. The progression and voicings are original production choices for this project, not an arrangement of a recorded composition.
