import io, re
base = "testing/sample_ui/"
css = io.open(base + "styles.css", encoding="utf-8").read()
print("CSS braces balanced:", css.count("{") == css.count("}"), "(", css.count("{"), "/", css.count("}"), ")")

html = io.open(base + "index.html", encoding="utf-8-sig").read()
ok = True
for tag in ["section", "div", "main", "aside", "nav", "table", "thead", "tbody", "header", "button", "select"]:
    o = len(re.findall(r"<" + tag + r"[\s>]", html))
    c = html.count("</" + tag + ">")
    if o != c:
        print(" Mismatch", tag, "open", o, "close", c)
        ok = False
print("HTMLL tags balanced:", ok)
print("has </html>:", html.rstrip().endswith("</html>"))