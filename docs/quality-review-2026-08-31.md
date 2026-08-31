# Fintech Pulse quality review — 31 August 2026

## Scope and evidence

Reviewed the supplied conversation, the production writer/renderer/intro scripts,
daily and backfill workflows, Episode 6's published show notes, and its MP3 duration
(665.425 seconds, approximately 11:05). This is NOT a claim that the audio has been
listened to end-to-end. The original spoken script is not in the repository; the
old workflow removed it and the renderer removed its individual blocks.

## Findings and local changes

1. **Brand:** the intro generator explicitly assigned `فنتك بلس.` to Sultan.
   Changed to `Fintech Pulse.` using Faisal (`wyC6KvCMTAXGbiCKlfSx`), with English
   selected for this short ident only. Existing music is reused. The old recorded
   asset is unchanged until a paid render runs; changing text alone does not fix it.
2. **Pronunciation:** instructions explicitly required colloquial number spellings.
   Replaced with formal Arabic number words and selective diacritics. Basic checks
   reject digits in speech, known bad spellings and a small set of dialect flags.
   These checks do not establish grammatical correctness or detect audible accents.
3. **Accent drift:** independent dialogue blocks, stability 0.35 and elaborate
   performance instructions are plausible contributors, not a proven causal account
   of the reported two-minute Egyptian section. Retained the chosen voices, changed
   stability to 0.5, added a Saudi accent cue on each speaker's first turn per block,
   and prevented silent model substitution. The cue is experimental and needs listening
   review; `language_code=ar` cannot select Najdi or guarantee an accent.
4. **Audience:** the old system prompt explicitly described one acquiring/onboarding
   product manager. Replaced with a broad Saudi/global fintech audience. Product
   explanations remain, but there is no mandatory acquiring angle.
5. **Coherence:** forced disagreement, a required change of mind and incomplete
   sentences encouraged theatrical/disjointed dialogue. Replaced with one opening
   question, two or three stories, logical bridges and a concrete product journey.
   Episode 6's notes listed roughly eight news subjects before its product segment.
6. **Length and recoverability:** removed destructive tail trimming; target 6,600
   spoken characters is an estimate calibrated from Episode 6. Final duration must
   be 570–630 seconds including music before entering `incoming`. Retain drafts,
   audio blocks and settings; archive on workflow failure. No speed-up to fit time.
7. **Intro clarity:** speech starts after the ident/music, at full level, with a short
   gap. A limiter prevents mix peaks above the configured ceiling. Synthetic-tone
   testing checks duration/mixing only, not human listening quality.
8. **Skipped days/duplicates:** daily downstream steps now run only when a new script
   actually exists. Failure to read the episode index stops generation instead of
   ignoring the error and risking duplicate spending.

## Preview prepared (NOT rendered)

`docs/drafts/quality-preview.json` is an evergreen Wise discussion, not a fabricated
news bulletin. It tests the English ident, both voices, formal “خمسة عشر”, mixed
English/Arabic, follow-up questions, and a render-block boundary. Its claim sources
are recorded in the JSON notes. The hypothetical fee is explicitly labelled.

`.github/workflows/quality-preview.yml` renders only this sample. It has read-only
repository permissions, uploads review artifacts, and never commits, builds the
feed, or publishes. GitHub artifact access follows repository permissions: it is
not a confidential storage service or a public podcast entry.

Listening approval must cover the ENTIRE sample, especially both sides of its block
boundary. If an accent cue is audible, changes voice identity or fails to prevent
drift, do not publish: adjust that block's delivery and listen again. A full episode
also needs end-to-end listening and source verification; passing unit tests does
not certify either.

## Verification and activation status

- 15 local tests pass, including a real ffmpeg synthetic-tone mix.
- Python compilation and whitespace checks pass.
- No ElevenLabs/Anthropic generation was run and no API credits were spent here.
- API keys are absent from this process; the existing production runs use GitHub secrets.
- No remote code changes, feed changes, deletions or schedule changes were made.
- Workspace instructions prohibit agent pushes. Activation and generation require
  either the user's push or explicit permission to push the changes and run the preview.
- Rollback: revert the local quality-change commit; existing published episodes are
  untouched. Do not delete downloaded audio or reset the repository to roll back code.

## Official references

- Dialogue request limits, language and seed controls:
  https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert
- Stability tradeoffs and accent tags (not guaranteed):
  https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices
- Accent drift and voice selection:
  https://help.elevenlabs.io/hc/en-us/articles/19631995406481-Why-does-my-voice-change-accent-or-language
- Preview product pricing claim:
  https://wise.com/us/pricing/send-money
