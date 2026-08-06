#!/usr/bin/env python3
"""
exec-brief QA gate script.
Usage: python3 qa-check.py <merged.json path> <report.html path>
Exit 0 = all checks pass. Exit 1 = failures found.
"""
import json, re, sys, os
from pathlib import Path

REQUIRED_ANCHORS = [
    "exec-summary", "calendar", "key-accounts", "dt-usage",
    "struggles", "consumption", "opportunities", "public-intelligence", "action-items"
]
JUNK_PATTERNS = [r'\$NaN', r'\bundefined\b', r'\[object Object\]', r'\$\$', r'%%']
LIGHT_MODE_FLIP = r'prefers-color-scheme\s*:\s*light'

def fail(msg):
    print(f"FAIL: {msg}")
    return False

def warn(msg):
    print(f"WARN: {msg}")

def ok(msg):
    print(f"  OK: {msg}")

def load_merged(path):
    with open(path) as f:
        return json.load(f)

def load_html(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def check_anchors(html, merged):
    passed = True
    for anchor in REQUIRED_ANCHORS:
        if f'id="{anchor}"' not in html and f"id='{anchor}'" not in html:
            passed = fail(f"Missing anchor #{anchor}") and False
        else:
            ok(f"Anchor #{anchor} present")
    return passed

def check_meeting_accounts(html, merged):
    passed = True
    cal = merged.get("calendar", {})
    upcoming = cal.get("upcomingMeetings", []) if isinstance(cal, dict) else []
    for mtg in upcoming:
        account = mtg.get("account")
        if not account:
            continue
        if f'data-account="{account}"' not in html and f"data-account='{account}'" not in html:
            passed = fail(f"Meeting account '{account}' has no stamped card in HTML") and False
        else:
            ok(f"Meeting account '{account}' card present")
    return passed

def check_stamps_attribution(html, merged):
    passed = True
    accounts = merged.get("accounts", [])
    ae_map = {a["account"]: a.get("ae", "") for a in accounts if "account" in a}
    pairs = re.findall(r'data-account=["\']([^"\']+)["\'][^>]*data-ae=["\']([^"\']+)["\']', html)
    pairs += re.findall(r'data-ae=["\']([^"\']+)["\'][^>]*data-account=["\']([^"\']+)["\']', html)
    for (acct, ae) in pairs:
        expected_ae = ae_map.get(acct)
        if expected_ae and ae and ae != expected_ae:
            passed = fail(f"Attribution mismatch: '{acct}' stamped AE='{ae}' but merged.json says AE='{expected_ae}'") and False
    if pairs:
        ok(f"Checked {len(pairs)} account stamp pairs")
    else:
        warn("No data-account+data-ae pairs found — synthesis may be missing stamps")
    return passed

def check_report_data_block(html):
    if 'id="report-data"' not in html and "id='report-data'" not in html:
        return fail("Missing <script id='report-data'> merged.json embed")
    ok("report-data block present")
    return True

def check_no_light_mode_flip(html):
    if re.search(LIGHT_MODE_FLIP, html):
        return fail("Found prefers-color-scheme:light — brand violation (dark canvas only)")
    ok("No light-mode CSS flip")
    return True

def check_logo(html, scratchpad=None):
    if "data:image/png;base64," not in html:
        return fail("DT logo base64 not embedded")
    ok("Logo base64 present")
    return True

def check_junk_patterns(html):
    passed = True
    for pattern in JUNK_PATTERNS:
        if re.search(pattern, html):
            passed = fail(f"Junk pattern found: {pattern}") and False
    if passed:
        ok("No junk patterns ($NaN, undefined, etc.)")
    return passed

def check_dom_containment(html):
    passed = True
    if "sidebar" not in html and "sidebar-nav" not in html:
        warn("No sidebar element found — layout may be missing")
    page_start = html.find('class="page"')
    if page_start == -1:
        page_start = html.find("class='page'")
    if page_start == -1:
        warn("No .page wrapper found — check two-column layout")
    else:
        for anchor in REQUIRED_ANCHORS:
            anchor_pos = html.find(f'id="{anchor}"')
            if anchor_pos == -1:
                anchor_pos = html.find(f"id='{anchor}'")
            if anchor_pos != -1 and anchor_pos < page_start:
                passed = fail(f"Section #{anchor} appears before .page wrapper — DOM containment error") and False
    if passed:
        ok("DOM containment check passed")
    return passed

def check_tag_balance(html):
    opens = html.count("<div") + html.count("<section")
    closes = html.count("</div>") + html.count("</section>")
    if opens != closes:
        return fail(f"Tag imbalance: {opens} opens vs {closes} closes (orphan tags may break layout)")
    ok(f"Tag balance OK ({opens} div/section pairs)")
    return True

def main():
    if len(sys.argv) < 3:
        print("Usage: qa-check.py <merged.json> <report.html>")
        sys.exit(1)
    merged_path = sys.argv[1]
    html_path = sys.argv[2]
    if not Path(merged_path).exists():
        print(f"FATAL: merged.json not found at {merged_path}")
        sys.exit(1)
    if not Path(html_path).exists():
        print(f"FATAL: HTML report not found at {html_path}")
        sys.exit(1)
    print(f"\nexec-brief QA Gate")
    print(f"  merged: {merged_path}")
    print(f"  report: {html_path}")
    print()
    merged = load_merged(merged_path)
    html = load_html(html_path)
    results = [
        check_anchors(html, merged),
        check_meeting_accounts(html, merged),
        check_stamps_attribution(html, merged),
        check_report_data_block(html),
        check_no_light_mode_flip(html),
        check_logo(html),
        check_junk_patterns(html),
        check_dom_containment(html),
        check_tag_balance(html),
    ]
    print()
    if all(results):
        print("QA PASS — all checks passed")
        sys.exit(0)
    else:
        failures = results.count(False)
        print(f"QA FAIL — {failures} check(s) failed. Fix and re-run.")
        sys.exit(1)

if __name__ == "__main__":
    main()
