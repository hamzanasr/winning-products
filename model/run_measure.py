# -*- coding: utf-8 -*-
"""Unattended measuring loop for the 100â€“200 SAR list. Safe to restart at any time.
Each cycle: refresh candidates (build_v3 --prep) -> supplier evidence -> Amazon.sa competition
(1 thread, polite delay) -> build_v3. Repeats every 10 minutes to pick up new idea files."""
import os, subprocess, sys, time, datetime
here = os.path.dirname(os.path.abspath(__file__)); repo = os.path.dirname(here); work = os.path.dirname(repo)
env = dict(os.environ, PYTHONIOENCODING="utf8", AMZ_THREADS="2", AMZ_DELAY="2.5")
log = open(os.path.join(work, "run_measure.log"), "a", encoding="utf-8")
def run(args, timeout):
    try:
        r = subprocess.run([sys.executable] + args, cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return (r.stdout or "").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        return ["timeout"]
while True:
    t = datetime.datetime.now().strftime("%H:%M")
    out = run(["model/build_v3.py", "--prep"], 900)
    out += run(["model/mic_enrich.py", "../v3_candidates.json", "data/mic_1500.json"], 7200)
    out += run(["model/amz_comp.py", "../v3_candidates.json", "data/amz_comp.json"], 7200)
    out += run(["model/build_v3.py"], 900)
    log.write(t + " | " + " | ".join(out) + "\n"); log.flush()
    time.sleep(600)

