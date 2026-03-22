#!/usr/bin/env python3
"""
fetch_wikidata.py — Polite bulk fetcher for Wikidata physical properties
========================================================================

Queries Wikidata for dimensions, mass, and material composition of every
common object Nagatha might ever need to map.  Results are written to:

    object_maps/wikidata_cache.json

This is a one-time (or occasional) operation.  Once the cache exists,
Nagatha reads it locally and never hits the network at runtime.

Rules of the road
─────────────────
- 0.6 s between search calls, 0.3 s between label-resolution calls
- Proper User-Agent header identifying the bot
- Checkpointing: saves after every 10 items so it can be interrupted
  and resumed without losing work
- Skips items already in the cache (unless --force is passed)

Usage
─────
    python agent/fetch_wikidata.py                  # fetch all missing
    python agent/fetch_wikidata.py banana           # fetch one item
    python agent/fetch_wikidata.py banana "coffee mug" kettle
    python agent/fetch_wikidata.py --force banana   # re-fetch even if cached
    python agent/fetch_wikidata.py --report         # show cache summary
    python agent/fetch_wikidata.py --all --force    # full refresh

Run from the MatterShaper/ directory.
"""

import sys
import time
from pathlib import Path

# Make sure we can import from agent/
sys.path.insert(0, str(Path(__file__).parent))
from object_db import WikidataFetcher, _normalise

# ── Master object list ────────────────────────────────────────────────────────
#
# Format: ("search term", "cache key")
# The search term is sent to Wikidata; the cache key is the normalised
# form stored in wikidata_cache.json.
#
# Tips for getting the right Wikidata item:
#   - Be specific: "chicken egg" not "egg" (egg is an abstract concept)
#   - Use common names: "ballpoint pen" not "biro"
#   - Avoid brand names — Wikidata has the generic object

OBJECTS = [
    # ── Kitchenware ───────────────────────────────────────────────────────────
    ("coffee mug",          "coffee_mug"),
    ("teacup",              "tea_cup"),
    ("wine glass",          "wine_glass"),
    ("drinking glass",      "water_glass"),
    ("ceramic plate",       "plate"),
    ("bowl",                "bowl"),
    ("table fork",          "fork"),
    ("table knife",         "knife"),
    ("tablespoon",          "spoon"),
    ("cooking pot",         "pot"),
    ("frying pan",          "frying_pan"),
    ("toaster",             "toaster"),
    ("electric kettle",     "kettle"),
    ("blender",             "blender"),
    ("kitchen knife",       "kitchen_knife"),
    ("cutting board",       "cutting_board"),
    ("colander",            "colander"),
    ("ladle",               "ladle"),
    ("rolling pin",         "rolling_pin"),

    # ── Furniture ─────────────────────────────────────────────────────────────
    ("dining chair",        "dining_chair"),
    ("office chair",        "office_chair"),
    ("writing desk",        "desk"),
    ("dining table",        "table"),
    ("bookcase",            "bookshelf"),
    ("bar stool",           "stool"),
    ("sofa",                "couch"),
    ("bed",                 "bed"),
    ("bedside table",       "nightstand"),
    ("chest of drawers",    "dresser"),
    ("television stand",    "tv_stand"),
    ("wardrobe",            "wardrobe"),
    ("coffee table",        "coffee_table"),
    ("armchair",            "armchair"),

    # ── Lighting ──────────────────────────────────────────────────────────────
    ("table lamp",          "desk_lamp"),
    ("floor lamp",          "floor_lamp"),
    ("ceiling fan",         "ceiling_fan"),
    ("candle",              "candle"),
    ("lantern",             "lantern"),
    ("light bulb",          "light_bulb"),

    # ── Electronics ───────────────────────────────────────────────────────────
    ("laptop computer",     "laptop"),
    ("computer monitor",    "monitor"),
    ("computer keyboard",   "keyboard"),
    ("computer mouse",      "mouse"),
    ("smartphone",          "phone"),
    ("tablet computer",     "tablet"),
    ("loudspeaker",         "speaker"),
    ("headphones",          "headphones"),
    ("television set",      "television"),
    ("camera",              "camera"),
    ("remote control",      "remote_control"),
    ("USB flash drive",     "usb_drive"),

    # ── Fruit & Food ──────────────────────────────────────────────────────────
    ("banana",              "banana"),
    ("apple",               "apple"),
    ("orange fruit",        "orange"),
    ("pear",                "pear"),
    ("watermelon",          "watermelon"),
    ("chicken egg",         "egg"),
    ("loaf of bread",       "bread_loaf"),
    ("pizza",               "pizza"),
    ("wine bottle",         "wine_bottle"),
    ("beer bottle",         "beer_bottle"),
    ("aluminium beverage can", "can"),
    ("lemon",               "lemon"),
    ("avocado",             "avocado"),
    ("tomato",              "tomato"),
    ("carrot",              "carrot"),
    ("cucumber",            "cucumber"),
    ("broccoli",            "broccoli"),
    ("coffee bean",         "coffee_bean"),

    # ── Drinkware ─────────────────────────────────────────────────────────────
    ("beer mug",            "beer_mug"),
    ("shot glass",          "shot_glass"),
    ("thermos",             "thermos"),
    ("water bottle",        "water_bottle"),

    # ── Office & Stationery ───────────────────────────────────────────────────
    ("pencil",              "pencil"),
    ("ballpoint pen",       "pen"),
    ("stapler",             "stapler"),
    ("adhesive tape dispenser", "tape_dispenser"),
    ("book",                "book"),
    ("ring binder",         "binder"),
    ("scissors",            "scissors"),
    ("ruler",               "ruler"),
    ("paper clip",          "paper_clip"),
    ("sticky note",         "sticky_note"),

    # ── Tools & Hardware ──────────────────────────────────────────────────────
    ("hammer",              "hammer"),
    ("screwdriver",         "screwdriver"),
    ("wrench",              "wrench"),
    ("tape measure",        "tape_measure"),
    ("power drill",         "power_drill"),
    ("flashlight",          "flashlight"),

    # ── Sports & Outdoor ──────────────────────────────────────────────────────
    ("fire hydrant",        "fire_hydrant"),
    ("letter box",          "mailbox"),
    ("waste bin",           "trash_can"),
    ("flower pot",          "flower_pot"),
    ("watering can",        "watering_can"),
    ("bicycle",             "bicycle"),
    ("tennis ball",         "tennis_ball"),
    ("basketball",          "basketball"),
    ("football",            "football"),
    ("baseball",            "baseball"),
    ("dumbbell",            "dumbbell"),
    ("yoga mat",            "yoga_mat"),

    # ── Bathroom ──────────────────────────────────────────────────────────────
    ("bar of soap",         "soap_bar"),
    ("toothbrush",          "toothbrush"),
    ("toilet paper roll",   "toilet_paper"),
    ("shampoo bottle",      "shampoo_bottle"),
    ("toothpaste tube",     "toothpaste"),

    # ── Containers & Misc ─────────────────────────────────────────────────────
    ("glass jar",           "glass_jar"),
    ("cardboard box",       "cardboard_box"),
    ("shopping bag",        "shopping_bag"),
    ("backpack",            "backpack"),
    ("suitcase",            "suitcase"),
    ("umbrella",            "umbrella"),
    ("wristwatch",          "wristwatch"),
    ("padlock",             "padlock"),
    ("key",                 "key"),
    ("coin",                "coin"),
]

TOTAL = len(OBJECTS)


# ── Helpers ───────────────────────────────────────────────────────────────────

def report(fetcher):
    cache = fetcher._cache.get("objects", {})
    total      = len(cache)
    has_dims   = sum(1 for v in cache.values()
                     if any(v.get(f) is not None
                            for f in ["height_m","width_m","length_m","diameter_m"]))
    has_mass   = sum(1 for v in cache.values() if v.get("mass_kg") is not None)
    has_mat    = sum(1 for v in cache.values() if v.get("materials"))
    no_data    = sum(1 for v in cache.values() if v.get("confidence") == "none")

    print(f"\n{'─'*60}")
    print(f"  Wikidata cache: {fetcher.CACHE_PATH}")
    print(f"  Objects cached : {total}")
    print(f"  Have dimensions: {has_dims}  ({has_dims/max(total,1):.0%})")
    print(f"  Have mass      : {has_mass}  ({has_mass/max(total,1):.0%})")
    print(f"  Have materials : {has_mat}  ({has_mat/max(total,1):.0%})")
    print(f"  No data found  : {no_data}  ({no_data/max(total,1):.0%})")
    print(f"{'─'*60}\n")

    if no_data:
        print("Items with no Wikidata data (may need better search terms):")
        for k, v in sorted(cache.items()):
            if v.get("confidence") == "none":
                print(f"  {k:<30}  searched: \"{v.get('search_term',k)}\"")
        print()


def fetch_one(fetcher, search_term, cache_key, force=False):
    """Fetch one item, print progress, return record."""
    if not force and fetcher.lookup(search_term.lower().replace(" ","_")) is not None:
        # Already cached under natural key — check by cache_key too
        existing = fetcher._cache.get("objects", {}).get(cache_key)
        if existing:
            conf = existing.get("confidence", "?")
            dims = sum(1 for f in ["height_m","width_m","length_m","diameter_m"]
                       if existing.get(f) is not None)
            print(f"  ✓ {cache_key:<30}  (cached — {conf}, {dims} dims)")
            return existing

    print(f"  → {cache_key:<30}  searching '{search_term}'...", end="", flush=True)
    record = fetcher.fetch_and_cache(search_term)

    # Store under cache_key explicitly (search may have found a slightly different key)
    fetcher._cache.setdefault("objects", {})[cache_key] = record
    fetcher._save_cache()

    conf  = record.get("confidence", "?")
    qid   = record.get("wikidata_id", "—")
    dims  = sum(1 for f in ["height_m","width_m","length_m","diameter_m","mass_kg"]
                if record.get(f) is not None)
    mats  = len(record.get("materials", []))
    label = record.get("wikidata_label", "?")

    print(f"  {qid:<12}  \"{label}\"  "
          f"dims:{dims}  mats:{mats}  [{conf}]")
    return record


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("items", nargs="*",
                   help="Specific item(s) to fetch (natural language names). "
                        "Omit to fetch all missing items.")
    p.add_argument("--all",    action="store_true",
                   help="Fetch every item in the master list")
    p.add_argument("--force",  action="store_true",
                   help="Re-fetch even if already in cache")
    p.add_argument("--report", action="store_true",
                   help="Print cache summary and exit")
    p.add_argument("--delay",  type=float, default=0.6,
                   help="Seconds between search requests (default 0.6)")
    args = p.parse_args()

    fetcher = WikidataFetcher()

    if args.report:
        report(fetcher)
        return

    # Decide which items to process
    if args.items:
        # Specific items given on command line
        targets = [(name, _normalise(name).replace(" ", "_"))
                   for name in args.items]
    elif args.all:
        targets = OBJECTS
    else:
        # Default: fetch everything in OBJECTS that isn't cached yet
        cached_keys = set(fetcher._cache.get("objects", {}).keys())
        targets = [(term, key) for term, key in OBJECTS
                   if key not in cached_keys]
        if not targets:
            print(f"\n[fetch_wikidata] Cache is complete ({TOTAL} items). "
                  f"Use --force to refresh.\n")
            report(fetcher)
            return

    print(f"\n[fetch_wikidata] Fetching {len(targets)} item(s) from Wikidata.")
    print(f"  Delay: {args.delay}s between requests.  Be polite.\n")

    checkpoint_every = 10
    for i, (term, key) in enumerate(targets, 1):
        fetch_one(fetcher, term, key, force=args.force)

        if i % checkpoint_every == 0:
            print(f"\n  — checkpoint ({i}/{len(targets)}) —\n")

        # Extra politeness delay between items
        if i < len(targets):
            time.sleep(args.delay)

    print(f"\n[fetch_wikidata] Done. {len(targets)} item(s) processed.\n")
    report(fetcher)


if __name__ == "__main__":
    main()
