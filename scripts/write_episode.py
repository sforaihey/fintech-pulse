"""Research today's fintech news and write the two-host script, in Najdi.

Runs in CI. Research uses authoritative Arabic and English sources; the script
is then composed in accessible Saudi Arabic using the editorial policy.

Output: episode.json  {"number", "date", "product", "stories", "notes",
                       "lines": [{"speaker": "سلطان"|"فيصل", "text": ...}]}
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "episode.json"
RAW = "https://raw.githubusercontent.com/sforaihey/fintech-pulse/main"

RIYADH = timezone(timedelta(hours=3))
MODEL = "claude-opus-5"
# Starting estimate calibrated from Ep. 06, not a duration guarantee.
# The renderer measures the final file, including the theme.
CHAR_BUDGET = int(os.environ.get("FINTECH_CHAR_BUDGET", "6600"))
# Backfill support: write an episode for a past date instead of today.
EPISODE_DATE = os.environ.get("FINTECH_DATE", "")
EPISODE_NUMBER = os.environ.get("FINTECH_EPISODE", "")

SYSTEM = (REPO / "scripts" / "editorial_policy.md").read_text()


def fetch(path: str) -> str:
    try:
        with urllib.request.urlopen(f"{RAW}/{path}", timeout=30) as response:
            return response.read().decode()
    except Exception as exc:                     # noqa: BLE001 - report and go on
        print(f"  warning: could not read {path}: {exc}")
        return ""


def next_episode_number() -> int:
    try:
        return max(int(k) for k in json.loads(fetch("episodes.json"))) + 1
    except Exception:                            # noqa: BLE001
        sys.exit("could not determine the next episode number from episodes.json")


def script_chars(lines) -> int:
    return sum(len(line["text"]) for line in lines)


AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
           "الجمعة", "السبت", "الأحد"]
AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def arabic_date(day, with_weekday: bool = True) -> str:
    """Dates in Arabic, so nothing English leaks into the title or notes."""
    stamp = f"{day.day} {AR_MONTHS[day.month - 1]} {day.year}"
    return f"{AR_DAYS[day.weekday()]} {stamp}" if with_weekday else stamp


def previous_publishing_day(day):
    """The last Sunday-to-Thursday day before `day`."""
    earlier = day - timedelta(days=1)
    while earlier.weekday() in (4, 5):
        earlier -= timedelta(days=1)
    return earlier


def build_prompt(number: int, today, covered: str, recent: str = "") -> str:
    covered_block = covered or "(ما فيه منتجات مغطاة بعد — اختر أي واحد)"
    recent_block = recent or "(ما فيه حلقات سابقة)"
    since = previous_publishing_day(today)
    span = (today - since).days
    window = (f"من الحلقة اللي طلعت يوم {arabic_date(since)} — يعني {span} أيام "
              f"أخبار، وفيها نهاية الأسبوع" if span > 1 else
              f"من الحلقة اللي طلعت يوم {arabic_date(since)}")

    return f"""اكتب حلقة رقم {number:02d} من "Fintech Pulse" ليوم \
{arabic_date(today)} بتوقيت الرياض.

ابحث في المصادر الأصلية بالعربية والإنجليزية، ثم جهّز الحقائق ومصادرها.
اكتب بعدها بعربية سعودية واضحة ولمسة نجدية خفيفة وفق السياسة التحريرية.

ابحث عن اللي صار {window}، لين صباح {arabic_date(today, False)}. اللي صار يوم الجمعة
أو السبت ما ينضاع — إذا هذي الحلقة بعد نهاية أسبوع، اليومين داخلين في نطاقك.
مجالين:
  (أ) السعودية — تنظيمات وتراخيص ساما، البنوك المحلية، المدفوعات، جولات
      تمويل الفنتك السعودية، وتحركات القطاع المالي ضمن رؤية ألفين وثلاثين.
  (ب) عالمياً — أي شي مهم فعلاً في المدفوعات، البنوك، العملات المستقرة
      والترميز، التمويل المدمج، أو الذكاء الاصطناعي في الخدمات المالية.

الأخبار اللي انقالت في حلقات قريبة — لا تعيدها كأنها جديدة. ترجع لها بس إذا
فيه جديد اليوم، وتبدأ بالجديد مو بإعادة الخبر:

{recent_block}

فقرة المنتج — في كل حلقة، للجمهور العام المهتم بالفنتك. اختر منتجًا حقيقيًا، مو
من هذي المغطاة:

{covered_block}

اشرحوه نقاش، مو محاضرة: فيصل يشرح وسلطان يسأل الأسئلة العملية ويجيب زاوية
ثانية. تعليمي ومتوازن، مو دعاية. غطّوا كل هذي، بأي ترتيب تجي فيه المحادثة:
  - وش يسوي المنتج، ومين يخدم
  - أي مشكلة يحل
  - تجربة العميل خطوة خطوة
  - كيف الشركة تكسب منه
  - قوته، حدوده، ومين ينافسه
  - درس واحد يستفيد منه أي شخص شغال في الفنتك
خلّ الفقرة تاخذ حوالي أربعين بالمية من الحلقة.

الطول: قارب {CHAR_BUDGET:,} حرف من الكلام المنطوق — يعني عشر دقايق تقريباً.
لا تحشي عشان توصل، ولا تستعجل عشان تنقص. عدد الأدوار يتبع المعنى، لا العكس.

الإيقاع: ردود مترابطة وجمل مكتملة المعنى، بدون افتعال خلاف أو مقاطعة.
لا تفرض عددًا من ردود الفعل. الأرقام المنطوقة كلمات فصيحة صحيحة نحويًا.
اختر خبرين أو ثلاثة فقط، واربط النقاش بسؤال واضح من البداية إلى الخاتمة.

الترتيب: افتتاحية قصيرة بأكبر خبر، ثم أخبار السعودية، ثم العالمية، ثم فقرة
المنتج، ثم خاتمة قصيرة تغلق سؤال البداية وتذكر ما نتابعه في يوم النشر القادم.
في notes سجّل تاريخ النشر وتاريخ الحدث لكل خبر، وروابط المصادر المؤيدة
لأرقام الأخبار وخصائص المنتج، وحسابات تحويل العملات. لا تكتف بقائمة روابط عامة.

رد بـ JSON فقط داخل ```json:
{{
  "title": "عنوان حقيقي للحلقة بالعربي — وش موضوع اليوم، مو تاريخ. من أربع
            إلى ثمان كلمات",
  "summary": "جملتين أو ثلاث بالعربي، اللي يقروها في تطبيق البودكاست عشان
              يقررون يسمعون. اذكر الأخبار الفعلية.",
  "product": "اسم المنتج اللي انشرح",
  "product_note": "سطر واحد لسجل المنتجات المغطاة",
  "stories": ["خبر", "خبر", "خبر"],
  "notes": "ملاحظات الحلقة بالماركداون، وفيها قائمة المصادر بالروابط",
  "lines": [{{"speaker": "سلطان", "text": "..."}}, ...]
}}"""


def call_claude(client, prompt: str):
    """One turn, resuming across pause_turn, with the fallback beta if allowed."""
    import anthropic
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}]
    kwargs = dict(model=MODEL, max_tokens=32000, system=SYSTEM,
                  thinking={"type": "adaptive"}, tools=tools)
    use_fallback = True

    for attempt in range(6):
        try:
            if use_fallback:
                stream = client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default", messages=messages, **kwargs)
            else:
                stream = client.messages.stream(messages=messages, **kwargs)
            with stream as active:
                message = active.get_final_message()
        except anthropic.BadRequestError as exc:
            if use_fallback:
                print(f"  fallback params rejected ({exc}); retrying without")
                use_fallback = False
                continue
            raise
        except anthropic.APIStatusError as exc:
            # Billing problems are the common one and deserve a plain sentence
            # rather than a traceback in a CI log nobody wants to read.
            if "credit balance" in str(exc) or "billing" in str(exc).lower():
                sys.exit("The Anthropic API account is out of credit. Top it up "
                         "at console.anthropic.com -> Plans & Billing. This is "
                         "separate from the Claude subscription and from "
                         "ElevenLabs.")
            raise

        if message.stop_reason == "refusal":
            sys.exit(f"request refused: {message.stop_details}")
        if message.stop_reason == "pause_turn":
            print("  pause_turn — resuming")
            messages += [{"role": "assistant", "content": message.content}]
            continue
        return message

    sys.exit("gave up after repeated pause_turn resumptions")


def extract_json(message) -> dict:
    text = "".join(b.text for b in message.content if b.type == "text")
    fenced = re.search(r"```json\s*(.+?)```", text, re.S)
    raw = fenced.group(1) if fenced else text[text.find("{"):text.rfind("}") + 1]
    return json.loads(raw)


def main() -> None:
    import anthropic
    from episode_quality import validate_lines
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")

    if EPISODE_DATE:
        today = date.fromisoformat(EPISODE_DATE)
        print(f"backfilling for {today:%A %-d %B %Y}")
    else:
        today = datetime.now(RIYADH).date()
        if today.weekday() in (4, 5):
            print(f"{today:%A} — the show runs Sunday to Thursday. Nothing to do.")
            return

    # GitHub's scheduler is best-effort: a firing can be hours late or skipped
    # entirely, so the workflow fires several times a morning. Whichever one
    # gets through first makes the episode; the rest find it already made.
    if not EPISODE_NUMBER:
        try:
            made = json.loads(fetch("episodes.json"))
            if any(e.get("date", "")[:10] == today.isoformat()
                   for e in made.values()):
                print(f"an episode for {today} already exists — nothing to do")
                return
        except Exception as exc:
            sys.exit(f"Cannot verify today's episode status; refusing duplicate spend: {exc}")

    number = int(EPISODE_NUMBER) if EPISODE_NUMBER else next_episode_number()
    covered = fetch("docs/products-covered.md")
    recent = fetch("docs/recent-stories.md")
    print(f"writing episode {number:02d} for {today}")

    client = anthropic.Anthropic(timeout=900.0)
    message = call_claude(client, build_prompt(number, today, covered, recent))
    response_path = REPO / '.render' / 'writer-response.json'
    response_path.parent.mkdir(exist_ok=True)
    response_path.write_text(message.model_dump_json(indent=2))
    print(f'  writer stop reason: {message.stop_reason}')
    episode = extract_json(message)
    draft = REPO / '.render' / 'writer-draft.json'
    draft.parent.mkdir(exist_ok=True)
    draft.write_text(json.dumps(episode, indent=2, ensure_ascii=False))
    validate_lines(episode.get("lines"))

    used = script_chars(episode["lines"])
    print(f"  {len(episode['lines'])} lines, {used:,} characters "
          f"(budget {CHAR_BUDGET:,})")

    # Preserve the complete draft. Never amputate the ending to satisfy a budget.
    ceiling = int(CHAR_BUDGET * 1.3)
    if used > ceiling:
        draft = REPO / ".render" / "overlength-draft.json"
        draft.parent.mkdir(exist_ok=True)
        draft.write_text(json.dumps(episode, indent=2, ensure_ascii=False))
        sys.exit(f"Draft exceeds {ceiling:,} characters; saved intact for editing: {draft}")

    episode.update(number=number, date=today.isoformat(),
                   characters=script_chars(episode["lines"]))
    OUT.write_text(json.dumps(episode, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT.name}")


if __name__ == "__main__":
    main()
