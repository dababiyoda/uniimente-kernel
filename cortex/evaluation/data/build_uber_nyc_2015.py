"""Rebuild ``uber_nyc_2015_halfhour.json.gz`` from its public source (P6 v5 natural family F8).

Source: every Uber pickup in New York City from January to June 2015, released by the NYC Taxi and Limousine
Commission (TLC) in response to a Freedom of Information Law (FOIL) request and published by FiveThirtyEight in
https://github.com/fivethirtyeight/uber-tlc-foil-response (``uber-trip-data/uber-raw-data-janjune-15.csv.zip``,
14.3 million rows: dispatching base, pickup date-time to the minute, affiliated base, TLC taxi-zone LocationID).
The zone of each pickup is resolved with the TLC zone table from the same repository
(``uber-trip-data/taxi-zone-lookup.csv``, CR line endings).

Terms: these are public records (NYC TLC via FOIL, published by FiveThirtyEight); neither the TLC nor
FiveThirtyEight states an open licence for this release. The extract is used for evaluation only; attribute the
NYC TLC and FiveThirtyEight; redistribution beyond evaluation is a founder decision.

The script checks both sha256 digests (any other bytes are refused), skips the ``__MACOSX`` resource-fork
members of the zip, and keeps only what the family needs: six disjoint pickup streams of 48 half-hour counts per
day for 2015-01-01..2015-06-30:

* ``Manhattan``, ``Brooklyn``, ``Bronx``                  zones whose TLC borough is that borough;
* ``Queens (excluding JFK and LaGuardia)``                Queens zones other than the two airports;
* ``JFK Airport``, ``LaGuardia Airport``                  those two zones.

Staten Island, Newark Airport (EWR) and the TLC's ``Unknown`` zones are left out and counted. The output is
written deterministically (sorted keys, compact separators, gzip mtime 0 and no file name), so a rebuild from the
same source gives the same bytes.

Clock (``CLOCK``): a block is a half hour of LOCAL WALL-CLOCK time in New York (America/New_York), read from the
text of ``Pickup_date``; block 0 is 00:00-00:30. Daylight saving time therefore shapes the extract: on 2015-03-08
(the second Sunday of March) the local hour 02:00-03:00 does not exist, so blocks 4 and 5 of that date hold zero
pickups in every stream. That zero is structural, not demand. ``local_block_seconds`` gives each block's real
length from the calendar alone (0 for a block of the hour that does not exist, 3600 for a block of the hour that
occurs twice when daylight saving time ends, 1800 otherwise); a consumer treats a 0-second block as missing, never
as a count (``run_v5.day_counts`` does). The extract's bytes record the counts as binned; the calendar, not a
change to the counts, says which blocks exist. No date in 2015-01-01..06-30 has a repeated hour.

Usage (the output is committed, so evaluation never downloads):

    python -I cortex/evaluation/data/build_uber_nyc_2015.py <uber-raw-data-janjune-15.csv.zip> <taxi-zone-lookup.csv>
    python -I cortex/evaluation/data/build_uber_nyc_2015.py --download <new empty directory>

``--download`` fetches both files into the named empty directory, checks their digests and builds from them.
"""
from __future__ import annotations

import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

REPO = "https://raw.githubusercontent.com/fivethirtyeight/uber-tlc-foil-response/master/uber-trip-data/"
TRIPS_URL = REPO + "uber-raw-data-janjune-15.csv.zip"
ZONES_URL = REPO + "taxi-zone-lookup.csv"
TRIPS_SHA256 = "b85c7373ce0b0186eb204e14600033033abf0b2ce47cc97b4ca59e1ec6ec8bec"
ZONES_SHA256 = "5dc91d7d4eb133ca6ce612a0ca9919383baf3193d879311ea459a10dd646e076"
MEMBER = "uber-raw-data-janjune-15.csv"
HEADER = ["Dispatching_base_num", "Pickup_date", "Affiliated_base_num", "locationID"]
OUT = Path(__file__).resolve().parent / "uber_nyc_2015_halfhour.json.gz"
FIRST, LAST = datetime.date(2015, 1, 1), datetime.date(2015, 6, 30)
BLOCKS = 48
BLOCK_SECONDS = 1800
CLOCK = ("local wall-clock time in New York (America/New_York), read from the text of Pickup_date; block b covers "
         "[b x 30 min, (b + 1) x 30 min) of the local day, so a block of an hour that does not exist (daylight saving "
         "time starts) is empty and a block of an hour that occurs twice (it ends) holds an hour of pickups")
AIRPORTS = {"JFK Airport": "JFK Airport", "LaGuardia Airport": "LaGuardia Airport"}
BOROUGHS = {"Manhattan": "Manhattan", "Brooklyn": "Brooklyn", "Bronx": "Bronx",
            "Queens": "Queens (excluding JFK and LaGuardia)"}
STREAMS = ("Manhattan", "Brooklyn", "Queens (excluding JFK and LaGuardia)", "Bronx", "JFK Airport",
           "LaGuardia Airport")
LICENCE = ("public records: NYC Taxi and Limousine Commission trip records released under the Freedom of "
           "Information Law and published by FiveThirtyEight (github.com/fivethirtyeight/uber-tlc-foil-response); "
           "no open licence is stated; evaluation use only; attribute the NYC TLC and FiveThirtyEight")


def _nth_sunday(year: int, month: int, n: int) -> datetime.date:
    first = datetime.date(year, month, 1)
    return first + datetime.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def local_block_seconds(day: str) -> list[int]:
    """Real elapsed seconds in each of the 48 local wall-clock half-hour blocks of ``day`` in New York, from the
    calendar alone (US rule in force since 2007: daylight saving time starts at 02:00 on the second Sunday of March,
    when the clock jumps to 03:00, and ends at 02:00 on the first Sunday of November, when it falls back to 01:00).
    1800 for an ordinary block; 0 for the two blocks of the hour that does not exist (02:00-03:00 on the start day);
    3600 for the two blocks of the hour that occurs twice (01:00-02:00 on the end day)."""
    d = datetime.date.fromisoformat(day)
    if d.year < 2007:
        raise ValueError("the daylight saving rule coded here is the one in force from 2007")
    seconds = [BLOCK_SECONDS] * BLOCKS
    if d == _nth_sunday(d.year, 3, 2):
        seconds[4] = seconds[5] = 0
    elif d == _nth_sunday(d.year, 11, 1):
        seconds[2] = seconds[3] = 2 * BLOCK_SECONDS
    return seconds


def _checked(path: Path, expected: str) -> bytes:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: sha256 {digest} differs from the recorded {expected}")
    return raw


def zone_streams(zones_raw: bytes) -> dict[int, str | None]:
    """LocationID -> stream name, or None for a zone outside every stream (Staten Island, EWR, Unknown)."""
    text = zones_raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        zone, borough = row["Zone"], row["Borough"]
        out[int(row["LocationID"])] = AIRPORTS.get(zone) or BOROUGHS.get(borough)
    if sorted(s for s in set(out.values()) if s) != sorted(STREAMS):
        raise SystemExit("the zone table does not yield the six declared streams")
    return out


def build(trips_zip: Path, zones_csv: Path) -> dict:
    stream_of = zone_streams(_checked(zones_csv, ZONES_SHA256))
    _checked(trips_zip, TRIPS_SHA256)
    dates = [(FIRST + datetime.timedelta(days=i)).isoformat() for i in range((LAST - FIRST).days + 1)]
    index = {d: i for i, d in enumerate(dates)}
    counts = {s: [[0] * BLOCKS for _ in dates] for s in STREAMS}
    left_out = {"outside_streams": 0, "unknown_location_id": 0, "outside_dates": 0}
    rows = 0
    with zipfile.ZipFile(trips_zip) as zf:
        members = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
        if members != [MEMBER]:
            raise SystemExit(f"unexpected zip members {members}")
        with zf.open(MEMBER) as fh:
            reader = csv.reader(io.TextIOWrapper(fh, encoding="utf-8", newline=""))
            if next(reader) != HEADER:
                raise SystemExit("unexpected header")
            for _, pickup, _, location in reader:
                rows += 1
                day, clock = pickup[:10], pickup[11:16]
                i = index.get(day)
                if i is None:
                    left_out["outside_dates"] += 1
                    continue
                location = int(location)
                if location not in stream_of:
                    left_out["unknown_location_id"] += 1
                    continue
                stream = stream_of[location]
                if stream is None:
                    left_out["outside_streams"] += 1
                    continue
                counts[stream][i][int(clock[:2]) * 2 + int(clock[3:5]) // 30] += 1
    kept = sum(sum(map(sum, days)) for days in counts.values())
    if kept + sum(left_out.values()) != rows:
        raise SystemExit("row accounting does not close")
    return {"schema": "greg-uber-nyc-2015-halfhour/1",
            "source": {"trips": {"url": TRIPS_URL, "sha256": TRIPS_SHA256, "member": MEMBER,
                                 "skipped_members": "__MACOSX/* (macOS resource forks)"},
                       "zones": {"url": ZONES_URL, "sha256": ZONES_SHA256}},
            "licence": LICENCE,
            "description": "Uber pickups in New York City per half-hour block (00:00-00:30 is block 0), six "
                           "disjoint streams by TLC taxi zone, 2015-01-01..2015-06-30",
            "streams_definition": {"Manhattan": "TLC borough Manhattan", "Brooklyn": "TLC borough Brooklyn",
                                   "Bronx": "TLC borough Bronx",
                                   "Queens (excluding JFK and LaGuardia)": "TLC borough Queens except zones JFK "
                                                                          "Airport (132) and LaGuardia Airport (138)",
                                   "JFK Airport": "TLC zone 132", "LaGuardia Airport": "TLC zone 138"},
            "rows": rows, "rows_kept": kept, "rows_left_out": left_out,
            "block_seconds": 1800, "dates": dates, "counts": counts}


def write(data: dict, out: Path = OUT) -> str:
    blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    with open(out, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, filename="") as gz:
            gz.write(blob)
    return hashlib.sha256(out.read_bytes()).hexdigest()


def download(directory: Path) -> tuple[Path, Path]:
    """Fetch both source files into an existing empty directory (their digests are checked by ``build``)."""
    import urllib.request
    directory = Path(directory)
    if not directory.is_dir() or any(directory.iterdir()):
        raise SystemExit(f"{directory} must be an existing empty directory")
    paths = []
    for url in (TRIPS_URL, ZONES_URL):
        target = directory / url.rsplit("/", 1)[1]
        with urllib.request.urlopen(url, timeout=600) as response, open(target, "wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
        paths.append(target)
    return paths[0], paths[1]


def main(argv):
    if len(argv) == 2 and argv[0] == "--download":
        trips, zones = download(Path(argv[1]))
    elif len(argv) == 2:
        trips, zones = Path(argv[0]), Path(argv[1])
    else:
        raise SystemExit(__doc__)
    data = build(trips, zones)
    digest = write(data)
    print(json.dumps({"out": str(OUT), "sha256": digest, "rows": data["rows"], "rows_kept": data["rows_kept"],
                      "rows_left_out": data["rows_left_out"], "days": len(data["dates"]),
                      "pickups_per_stream": {s: sum(map(sum, data["counts"][s])) for s in STREAMS}}))


if __name__ == "__main__":
    main(sys.argv[1:])
