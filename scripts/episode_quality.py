"""Cheap preflight checks, not a substitute for factual or listening review."""
import math
import re

SPEAKERS = {'سلطان', 'فيصل'}
# Deliberately conservative: these are spelling/dialect flags, not an accent detector.
FLAGGED = re.compile(r'فنتك\s+بلس|خمس[تط]عش\w*|(?<!\w)(?:عايز|عاوز|دلوقتي|كده|إزاي|ازاي|مش)(?!\w)')


def validate_lines(lines):
    if not isinstance(lines, list) or not lines:
        raise ValueError('Script must contain dialogue lines')
    for index, line in enumerate(lines, 1):
        if line.get('speaker') not in SPEAKERS:
            raise ValueError(f'Unknown speaker at line {index}')
        text = line.get('text', '')
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'Empty speech at line {index}')
        if re.search(r'\d', text):
            raise ValueError(f'Line {index}: write spoken numbers in formal Arabic words')
        if FLAGGED.search(text):
            raise ValueError(f'Line {index}: review brand, number spelling, or dialect')


def validate_duration(seconds):
    if not math.isfinite(seconds) or not 570 <= seconds <= 630:
        raise ValueError(f'Finished episode is {seconds:.1f}s; target is 570–630s. '
                         'Keep the audio for review; do not publish or accelerate speech.')
