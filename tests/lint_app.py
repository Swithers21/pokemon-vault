"""Looks through the website's script for mistakes the browser would only trip over when someone reaches that part of the page:
a name that doesn't exist (typos), a repeated key, code that can never run. Needs Node (npx fetches ESLint the first time).

    python tests/lint_app.py [index.html]
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = ["no-undef", "no-dupe-keys", "no-dupe-args", "no-dupe-else-if", "no-duplicate-case", "no-unreachable", "no-const-assign",
         "no-func-assign", "no-self-assign", "no-unsafe-negation", "valid-typeof", "use-isnan", "no-redeclare", "no-import-assign",
         "no-unsafe-finally", "no-sparse-arrays", "no-invalid-regexp", "no-misleading-character-class"]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "index.html")
    html = open(path, encoding="utf-8").read()
    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    if not scripts:
        print("No script found in", path)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        js = os.path.join(tmp, "app.js")
        with open(js, "w", encoding="utf-8") as f:
            f.write("\n".join(scripts))
        cmd = ["npx", "--yes", "eslint@8.57.0", "--no-eslintrc", "--env", "browser,es2022", "--parser-options", "ecmaVersion:2022", "--format", "unix"]
        for r in RULES:
            cmd += ["--rule", "%s:error" % r]
        cmd.append(js)
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp)
        out = (res.stdout + res.stderr).replace(js, "index.html(script)")
        if res.returncode == 0:
            print("The website's script has no undefined names or other slips.")
            return 0
        print(out.strip())
        return 1


if __name__ == "__main__":
    sys.exit(main())
