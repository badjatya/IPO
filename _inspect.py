import re, glob

def show(roots, want, ctx=220, max_show=4):
    for root in roots:
        for f in glob.glob(root + "/**/*.mjs", recursive=True):
            try:
                s = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if want not in s:
                continue
            print("====", f)
            shown = 0
            for m in re.finditer(re.escape(want), s):
                i = m.start()
                print("----", s[max(0, i - ctx) : i + ctx * 3].replace("\n", " "))
                shown += 1
                if shown >= max_show:
                    break

show(["web/node_modules/better-auth/dist"], "resetCredentialPassword", ctx=200, max_show=6)