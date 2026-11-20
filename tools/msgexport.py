"""Export all Splatoon message text of one language to JSON for translation.

    uv run python tools/msgexport.py <content dir> <lang> <out.json>
    e.g. uv run python tools/msgexport.py "Splatoon [AGMP01]/content" EUen work/text_EUen.json

Output: {"CommonMsg": {"Talk/TalkShop.msbt": {"label": "text", ...}, ...}, "LayoutMsg": {...}}
Control tags are written as {group:type:hexparams}, closing tags {/group:type};
literal braces are doubled. Keep tags intact when translating.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from nin import Msbt, Sarc, load, tokens_to_str


def main(content, lang, out):
    result = {}
    total = chars = 0
    for arc in ("CommonMsg", "LayoutMsg"):
        sarc = Sarc(load(Path(content) / "Message" / f"{arc}_{lang}.szs"))
        result[arc] = {}
        for nm in sorted(sarc.files):
            msgs = {}
            for lbl, toks in Msbt(sarc.files[nm]).items():
                msgs[lbl] = tokens_to_str(toks)
                total += 1
                chars += sum(len(t) for t in toks if isinstance(t, str))
            result[arc][nm] = msgs
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{total} messages, {chars} characters of text -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__); sys.exit(1)
    main(*sys.argv[1:])
