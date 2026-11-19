"""Runs the automatic checks of the website in a real browser (desktop and phone size) against a made-up card list.

    python tests/run_tests.py             every check
    python tests/run_tests.py --smoke     only the quick must-never-break checks
    python tests/run_tests.py --only rapid    only checks with "rapid" in their name

Exit code 0 when everything passed, 1 when something failed. Needs: pip install playwright && playwright install chromium
"""
import argparse
import os
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness  # noqa: E402
import test_core  # noqa: F401,E402
import test_features  # noqa: F401,E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="only the quick checks that must never break")
    ap.add_argument("--only", default="", help="only checks whose name contains this")
    ap.add_argument("--retries", type=int, default=1, help="how many times to run a failed check again (timing can vary on a busy machine)")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    jobs = []
    for t in harness.TESTS:
        if args.smoke and not t["smoke"]:
            continue
        if args.only and args.only.lower() not in t["name"].lower():
            continue
        for kind in (["desktop", "phone"] if t["phone"] else ["desktop"]):
            jobs.append((t, kind))
    if not jobs:
        print("No checks match.")
        return 1

    failures, started = [], time.time()
    with tempfile.TemporaryDirectory() as with_data, tempfile.TemporaryDirectory() as without_data:
        harness.make_site(with_data)
        harness.make_site(without_data, mock=False)
        with harness.serve(with_data) as url, harness.serve(without_data) as url_no_data:
            browser = harness.Browser(url, headless=not args.headed)
            browser.no_data_url = url_no_data
            try:
                for t, kind in jobs:
                    label = "%s [%s]" % (t["name"], kind)
                    tries, error = 0, None
                    while tries <= args.retries:
                        t0 = time.time()
                        try:
                            t["fn"](browser, kind)
                            error = None
                            break
                        except Exception as e:  # noqa: BLE001 (any failure is a failed check)
                            error = "".join(traceback.format_exception_only(type(e), e)).strip()
                            tries += 1
                    if error:
                        failures.append((label, error))
                        print("FAIL  %s\n      %s" % (label, error.replace("\n", "\n      ")))
                    else:
                        print("ok    %s  (%.1fs%s)" % (label, time.time() - t0, ", passed on a second try" if tries else ""))
            finally:
                browser.close()
    print("\n%d checks, %d failed, %.0f seconds" % (len(jobs), len(failures), time.time() - started))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
