"""This container's real browsers with the headless shell absent (as on a body that has only full Chrome builds):
how long the first browser.render takes, what it returns, and what the second call costs. Then: processes left."""
import json, os, subprocess, sys, time
sys.path.insert(0, os.getcwd())
from greg import capabilities
capabilities.HEADLESS_SHELLS = "no-such-dir-*/x"          # the headless shell is not installed
print(json.dumps({"candidates": capabilities.chrome_candidates()}))
for call in (1, 2):
    t = time.monotonic()
    try:
        r = capabilities.chrome_binary()
    except capabilities.CapabilityError as exc:
        r = "CapabilityError: " + str(exc)
    print(json.dumps({"call": call, "seconds": round(time.monotonic() - t, 1), "result": r}), flush=True)
    if call == 1:
        left = subprocess.run("ps -eo pid,ppid,etimes,args | grep -c '[g]reg-browser-check-'", shell=True, capture_output=True, text=True).stdout.strip()
        dirs = [d for d in os.listdir("/tmp") if d.startswith("greg-browser-check-")]
        print(json.dumps({"processes_still_naming_the_check_profile": left, "check_profiles_left_in_tmp": dirs}), flush=True)
time.sleep(3)
left = subprocess.run("ps -eo pid,ppid,etimes,args | grep '[g]reg-browser-check-' | cut -c1-150", shell=True, capture_output=True, text=True).stdout
print(json.dumps({"after_3s_processes": left.splitlines()[:5], "check_profiles_left_in_tmp": [d for d in os.listdir("/tmp") if d.startswith("greg-browser-check-")]}))
