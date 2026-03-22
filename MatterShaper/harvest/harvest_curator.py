"""
Harvest Curator — Nagatha's Collection Manager
=================================================
Scans a local ShapeNet directory, picks one object at a time,
converts it to Sigma Signature format, auto-approves if quality
meets threshold, then waits a random interval before browsing
for the next one. Continues until every object has been examined.

She takes her time. But she doesn't agonize.

Design principles:
  - One at a time, never rushed
  - Random intervals between picks (she's browsing, not grinding)
  - Thorough analysis but with anti-paralysis limits
  - Auto-approve above quality threshold, reject below, flag in between
  - Full logging of every decision
  - Graceful stop/resume — can be interrupted and pick up later
  - Runs locally, no network needed after initial download

"One does not simply pillage a dataset.
 We examine each piece on its merits."

Anti-Analysis-Paralysis Protocol:
  - MAX_ANALYSIS_PASSES: She gets 3 tries to fit an object. Not 30.
  - DECISION_DEADLINE: After all passes, she MUST decide. Approve, reject, or flag.
  - MIN_CONFIDENCE: Below this, don't waste more passes — reject early.
  - GOOD_ENOUGH: Above this, approve on first pass — don't second-guess.
  - MAX_SECONDS_PER_OBJECT: Wall-clock timeout. Move on.
"""

import os
import sys
import json
import time
import random
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Add parent paths so imports work when run standalone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from obj_parser import scan_for_objs, parse_obj
from mesh_to_sigma import MeshToSigma, convert_single
from primitive_fitter import compute_fit_quality


# ── Configuration ────────────────────────────────────────────────

class HarvestConfig:
    """
    Nagatha's operating parameters.
    Tuned for thoroughness without paralysis.
    """

    # ─ Pace ─────────────────────────────────────────────────────
    MIN_INTERVAL_SECONDS = 2       # Minimum pause between objects
    MAX_INTERVAL_SECONDS = 30      # Maximum pause (she's browsing)
    # In practice: random.uniform(MIN, MAX) between each pick

    # ─ Anti-Paralysis Limits ────────────────────────────────────
    MAX_ANALYSIS_PASSES = 3        # Maximum re-analysis attempts per object
    MAX_SECONDS_PER_OBJECT = 120   # Wall-clock timeout per object (2 min)
    DECISION_DEADLINE = True       # After max passes, she MUST decide

    # ─ Quality Thresholds ───────────────────────────────────────
    GOOD_ENOUGH = 0.70             # Above this → approve on first pass
    ACCEPTABLE = 0.50              # Above this → try another pass, maybe approve
    MIN_CONFIDENCE = 0.30          # Below this → reject early, don't waste time
    MIN_PRIMITIVES = 3             # Need at least this many to be useful

    # ─ Auto-Approval ────────────────────────────────────────────
    AUTO_APPROVE = True            # If True, approve good objects without asking
    AUTO_REJECT = True             # If True, reject bad objects without asking
    FLAG_UNCERTAIN = True          # If True, flag borderline objects for review

    # ─ Output ───────────────────────────────────────────────────
    NORMALIZE_HEIGHT = 1.0         # Scale all objects to this height
    LOG_FILE = "harvest_log.json"  # Decision log

    def summary(self) -> str:
        return (
            f"Pace: {self.MIN_INTERVAL_SECONDS}-{self.MAX_INTERVAL_SECONDS}s between objects\n"
            f"Paralysis limits: {self.MAX_ANALYSIS_PASSES} passes, "
            f"{self.MAX_SECONDS_PER_OBJECT}s timeout\n"
            f"Quality: approve ≥{self.GOOD_ENOUGH:.0%}, "
            f"reject <{self.MIN_CONFIDENCE:.0%}, "
            f"review {self.MIN_CONFIDENCE:.0%}-{self.GOOD_ENOUGH:.0%}"
        )


# ── Decision Types ───────────────────────────────────────────────

class Decision:
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged_for_review"
    SKIPPED = "skipped"       # Already processed
    ERROR = "error"           # Couldn't process at all
    TIMEOUT = "timeout"       # Analysis paralysis prevention kicked in


# ── Harvest Log ──────────────────────────────────────────────────

class HarvestLog:
    """
    Persistent record of every object Nagatha has examined.
    Enables resume-after-interrupt and prevents re-processing.
    """

    def __init__(self, log_path: str):
        self.log_path = log_path
        self.entries: Dict[str, dict] = {}  # keyed by file hash
        self._load()

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    data = json.load(f)
                    self.entries = data.get("entries", {})
            except (json.JSONDecodeError, IOError):
                self.entries = {}

    def _save(self):
        data = {
            "curator": "Nagatha",
            "version": "1.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_examined": len(self.entries),
            "total_approved": sum(1 for e in self.entries.values()
                                 if e.get("decision") == Decision.APPROVED),
            "total_rejected": sum(1 for e in self.entries.values()
                                 if e.get("decision") == Decision.REJECTED),
            "total_flagged": sum(1 for e in self.entries.values()
                                if e.get("decision") == Decision.FLAGGED),
            "entries": self.entries
        }
        with open(self.log_path, 'w') as f:
            json.dump(data, f, indent=2)

    def is_processed(self, file_hash: str) -> bool:
        return file_hash in self.entries

    def record(self, file_hash: str, entry: dict):
        self.entries[file_hash] = entry
        self._save()

    @property
    def stats(self) -> dict:
        approved = sum(1 for e in self.entries.values()
                      if e.get("decision") == Decision.APPROVED)
        rejected = sum(1 for e in self.entries.values()
                      if e.get("decision") == Decision.REJECTED)
        flagged = sum(1 for e in self.entries.values()
                     if e.get("decision") == Decision.FLAGGED)
        errors = sum(1 for e in self.entries.values()
                    if e.get("decision") in (Decision.ERROR, Decision.TIMEOUT))
        return {
            "examined": len(self.entries),
            "approved": approved,
            "rejected": rejected,
            "flagged": flagged,
            "errors": errors
        }


# ── File Hashing ─────────────────────────────────────────────────

def file_hash(filepath: str) -> str:
    """Quick hash of file path + size (not full content — too slow for large meshes)."""
    stat = os.stat(filepath)
    key = f"{filepath}:{stat.st_size}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ── Library Index Integration ────────────────────────────────────

class LibraryManager:
    """
    Manages the Sigma library index.
    Adds new objects, tracks provenance.
    """

    def __init__(self, library_dir: str, index_path: str = None):
        self.library_dir = library_dir
        self.index_path = index_path or os.path.join(library_dir, "library_index.json")
        self.index = self._load_index()

    def _load_index(self) -> dict:
        if os.path.exists(self.index_path):
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {
            "version": "1.0",
            "engine": "MatterShaper",
            "format": "Sigma Signature v1",
            "agent": "Nagatha",
            "objects": {}
        }

    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)

    def has_object(self, key: str) -> bool:
        return key in self.index.get("objects", {})

    def add_object(self, key: str, name: str, shape_path: str,
                   color_path: str, primitive_count: int,
                   material_count: int, source: str = "shapenet_harvest",
                   quality_rating: str = "good"):
        """Register a new object in the library."""
        # Make paths relative to library dir
        rel_shape = os.path.relpath(shape_path, os.path.dirname(self.index_path))
        rel_color = os.path.relpath(color_path, os.path.dirname(self.index_path))

        self.index.setdefault("objects", {})[key] = {
            "key": key,
            "name": name,
            "aliases": _generate_aliases(name),
            "shape_path": rel_shape,
            "color_path": rel_color,
            "primitives": primitive_count,
            "materials": material_count,
            "approved": True,
            "approved_by": "Nagatha (auto)",
            "approved_date": datetime.now(timezone.utc).isoformat(),
            "created_by": "nagatha_harvest_v1",
            "source": source,
            "quality_rating": quality_rating
        }
        self._save_index()

    @property
    def object_count(self) -> int:
        return len(self.index.get("objects", {}))


def _generate_aliases(name: str) -> List[str]:
    """Generate search aliases from an object name."""
    aliases = [name.lower()]
    # Add individual words
    words = name.lower().replace('_', ' ').replace('-', ' ').split()
    for w in words:
        if w not in aliases and len(w) > 2:
            aliases.append(w)
    # Add without underscores
    clean = name.lower().replace('_', ' ')
    if clean not in aliases:
        aliases.append(clean)
    return aliases


# ── The Curator ──────────────────────────────────────────────────

class HarvestCurator:
    """
    Nagatha's harvest curator.

    Browses a local ShapeNet directory one object at a time,
    converts each to Sigma format, decides whether to approve,
    and moves on at a comfortable pace.

    She's thorough. But she's not neurotic.
    """

    def __init__(self, shapenet_dir: str, output_dir: str,
                 library_dir: str = None, config: HarvestConfig = None):
        self.shapenet_dir = shapenet_dir
        self.output_dir = output_dir
        self.library_dir = library_dir or output_dir
        self.config = config or HarvestConfig()
        self.converter = MeshToSigma(
            normalize_height=self.config.NORMALIZE_HEIGHT,
            verbose=True
        )

        # Initialize log and library
        log_path = os.path.join(output_dir, self.config.LOG_FILE)
        self.log = HarvestLog(log_path)

        index_path = os.path.join(self.library_dir, "library_index.json")
        self.library = LibraryManager(self.library_dir, index_path)

        # Track state
        self._running = False
        self._total_available = 0
        self._current_file = None

    def browse(self, max_objects: int = None, shuffle: bool = True):
        """
        Start browsing the ShapeNet directory.

        Picks one object at a time, converts it, decides on it,
        pauses, then picks another. Continues until:
          - All objects examined, or
          - max_objects reached, or
          - interrupted

        Args:
            max_objects: Stop after this many (None = process all)
            shuffle: If True, randomize the order (Nagatha browses, doesn't march)
        """
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║  N A G A T H A  —  H A R V E S T  C U R A T O R ║")
        print("╚══════════════════════════════════════════════════╝")
        print()

        # Scan for OBJ files
        print("  [Nagatha] Let me have a look at what's available...")
        all_objs = scan_for_objs(self.shapenet_dir)
        self._total_available = len(all_objs)

        if not all_objs:
            print(f"  [Nagatha] The cupboard is bare. No OBJ files in {self.shapenet_dir}.")
            return

        print(f"  [Nagatha] {len(all_objs):,} objects in the collection.")
        print(f"           {self.log.stats['examined']} already examined.")

        # Filter out already-processed
        pending = [f for f in all_objs if not self.log.is_processed(file_hash(f))]

        if not pending:
            stats = self.log.stats
            print(f"\n  [Nagatha] I've been through them all, actually.")
            print(f"           {stats['approved']} approved, "
                  f"{stats['rejected']} rejected, "
                  f"{stats['flagged']} flagged for your review.")
            print(f"           The collection is complete.")
            return

        print(f"  [Nagatha] {len(pending):,} still to examine.")
        print(f"  [Nagatha] {self.config.summary()}")
        print()

        if shuffle:
            random.shuffle(pending)

        self._running = True
        processed = 0

        for obj_path in pending:
            if not self._running:
                break
            if max_objects is not None and processed >= max_objects:
                break

            # ── Pick one ─────────────────────────────────────────
            self._current_file = obj_path
            rel_path = os.path.relpath(obj_path, self.shapenet_dir)
            fhash = file_hash(obj_path)

            print(f"  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌")
            print(f"  [Nagatha] Object {processed + 1}: {rel_path}")
            print()

            # ── Examine it ───────────────────────────────────────
            result = self._examine_object(obj_path, fhash)

            # ── Log the decision ─────────────────────────────────
            self.log.record(fhash, result)
            processed += 1

            # Show running stats
            stats = self.log.stats
            print(f"\n  [Nagatha] Running tally: {stats['approved']} approved, "
                  f"{stats['rejected']} rejected, {stats['flagged']} flagged. "
                  f"{len(pending) - processed} remaining.")

            # ── Pause before next (she's browsing, not sprinting) ─
            if processed < len(pending) and (max_objects is None or processed < max_objects):
                pause = random.uniform(
                    self.config.MIN_INTERVAL_SECONDS,
                    self.config.MAX_INTERVAL_SECONDS
                )
                print(f"  [Nagatha] Taking a moment... ({pause:.0f}s)")
                try:
                    time.sleep(pause)
                except KeyboardInterrupt:
                    print(f"\n  [Nagatha] Interrupted. I'll remember where we left off.")
                    self._running = False
                    break

        # ── Final report ─────────────────────────────────────────
        print()
        print("  ════════════════════════════════════════════════")
        stats = self.log.stats
        print(f"  [Nagatha] Session complete.")
        print(f"           Examined: {processed}")
        print(f"           Approved: {stats['approved']}")
        print(f"           Rejected: {stats['rejected']}")
        print(f"           Flagged:  {stats['flagged']}")
        print(f"           Library now holds {self.library.object_count} objects.")
        print(f"  ════════════════════════════════════════════════")

    def _examine_object(self, obj_path: str, fhash: str) -> dict:
        """
        Examine a single object. May take multiple passes.
        Returns a log entry dict.

        Anti-paralysis protocol:
        - Pass 1: Convert and assess. If GOOD_ENOUGH → approve immediately.
        - Pass 2-3: Only if borderline. Try re-segmenting.
        - After MAX_PASSES: forced decision based on best result so far.
        - Timeout: if wall-clock exceeds limit, stop and decide on what we have.
        """
        start_time = time.time()
        best_result = None
        best_quality = 0.0
        pass_count = 0

        for attempt in range(self.config.MAX_ANALYSIS_PASSES):
            # ── Wall-clock check ─────────────────────────────────
            elapsed = time.time() - start_time
            if elapsed > self.config.MAX_SECONDS_PER_OBJECT:
                print(f"  [Nagatha] I've spent long enough on this one. "
                      f"Time to decide. ({elapsed:.0f}s)")
                break

            pass_count = attempt + 1

            # ── Convert ──────────────────────────────────────────
            try:
                obj_name = self._derive_name(obj_path)
                result = self.converter.convert(
                    obj_path,
                    output_dir=self.output_dir,
                    object_name=obj_name
                )
            except Exception as e:
                print(f"  [Nagatha] Something went wrong: {e}")
                return self._make_entry(obj_path, fhash, Decision.ERROR,
                                       passes=pass_count, error=str(e))

            if result is None:
                print(f"  [Nagatha] Couldn't make anything of it.")
                return self._make_entry(obj_path, fhash, Decision.REJECTED,
                                       passes=pass_count,
                                       reason="conversion_failed")

            quality_score = result['quality']['avg_confidence']

            # Track best attempt
            if quality_score > best_quality:
                best_quality = quality_score
                best_result = result

            # ── Decision logic ───────────────────────────────────

            # Quick approve: clearly good enough
            if quality_score >= self.config.GOOD_ENOUGH:
                print(f"  [Nagatha] That's rather good. Approved on pass {pass_count}.")
                return self._approve(obj_path, fhash, result, pass_count)

            # Quick reject: clearly not going to work
            if quality_score < self.config.MIN_CONFIDENCE:
                print(f"  [Nagatha] I'm afraid this one's beyond salvaging. "
                      f"({quality_score:.0%} confidence)")
                return self._make_entry(obj_path, fhash, Decision.REJECTED,
                                       passes=pass_count,
                                       reason="below_minimum_confidence",
                                       quality=quality_score)

            # Borderline — try another pass if we have passes left
            if attempt < self.config.MAX_ANALYSIS_PASSES - 1:
                print(f"  [Nagatha] Hmm, {quality_score:.0%} confidence. "
                      f"Let me try a different approach...")
            # else: falls through to forced decision below

        # ── Forced decision (anti-paralysis) ─────────────────────
        if best_result is not None:
            if best_quality >= self.config.ACCEPTABLE:
                print(f"  [Nagatha] Best I can manage is {best_quality:.0%}. "
                      f"Acceptable. Approved after {pass_count} passes.")
                return self._approve(obj_path, fhash, best_result, pass_count)
            elif self.config.FLAG_UNCERTAIN:
                print(f"  [Nagatha] {best_quality:.0%} — I'm not entirely sure about this one. "
                      f"Flagging for your review, Aaron.")
                return self._make_entry(obj_path, fhash, Decision.FLAGGED,
                                       passes=pass_count,
                                       reason="borderline_quality",
                                       quality=best_quality)
            else:
                print(f"  [Nagatha] {best_quality:.0%}. Not up to standard. Rejected.")
                return self._make_entry(obj_path, fhash, Decision.REJECTED,
                                       passes=pass_count,
                                       reason="below_acceptable",
                                       quality=best_quality)

        return self._make_entry(obj_path, fhash, Decision.ERROR,
                               passes=pass_count, error="no_result_produced")

    def _approve(self, obj_path: str, fhash: str, result: dict,
                 passes: int) -> dict:
        """Approve an object and add it to the library."""
        name = result['name']
        display_name = name.replace('_', ' ').title()

        # Register in library
        self.library.add_object(
            key=name,
            name=display_name,
            shape_path=result['shape_path'],
            color_path=result['color_path'],
            primitive_count=result['primitive_count'],
            material_count=len(result['color_map'].get('materials', {})),
            source="shapenet_harvest",
            quality_rating=result['quality']['coverage_rating']
        )

        print(f"  [Nagatha] Into the library it goes. "
              f"Welcome home, little {display_name}.")

        return self._make_entry(
            obj_path, fhash, Decision.APPROVED,
            passes=passes,
            quality=result['quality']['avg_confidence'],
            primitive_count=result['primitive_count'],
            object_key=name
        )

    def _derive_name(self, obj_path: str) -> str:
        """
        Derive an object name from the file path.
        ShapeNet structure: category_id/model_id/models/model_normalized.obj
        """
        parts = obj_path.replace('\\', '/').split('/')

        # Try to find meaningful name from path
        # ShapeNet: synsetId/modelId/models/model_normalized.obj
        name_parts = []
        for p in parts:
            if p in ('models', 'model_normalized.obj', 'model.obj'):
                continue
            if len(p) > 4 and not p.endswith('.obj'):
                name_parts.append(p)

        if name_parts:
            name = '_'.join(name_parts[-2:])  # Use last 2 meaningful parts
        else:
            name = os.path.splitext(os.path.basename(obj_path))[0]

        # Clean up
        name = name.replace('-', '_').replace(' ', '_').lower()
        # Truncate if too long
        if len(name) > 60:
            name = name[:60]

        return name

    def _make_entry(self, obj_path: str, fhash: str, decision: str,
                    passes: int = 0, reason: str = None,
                    quality: float = None, error: str = None,
                    primitive_count: int = None,
                    object_key: str = None) -> dict:
        """Build a log entry."""
        entry = {
            "file": obj_path,
            "hash": fhash,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "passes": passes,
            "curator": "Nagatha"
        }
        if reason:
            entry["reason"] = reason
        if quality is not None:
            entry["quality"] = round(quality, 3)
        if error:
            entry["error"] = error
        if primitive_count is not None:
            entry["primitive_count"] = primitive_count
        if object_key:
            entry["object_key"] = object_key
        return entry

    def stop(self):
        """Graceful stop — finishes current object, then halts."""
        print(f"  [Nagatha] Wrapping up the current piece, then I'll stop.")
        self._running = False

    def status(self) -> str:
        """Current status report."""
        stats = self.log.stats
        return (
            f"Collection: {self._total_available:,} objects available\n"
            f"Examined: {stats['examined']}\n"
            f"Approved: {stats['approved']} | Rejected: {stats['rejected']} | "
            f"Flagged: {stats['flagged']} | Errors: {stats['errors']}\n"
            f"Library: {self.library.object_count} objects\n"
            f"Currently: {'examining ' + str(self._current_file) if self._running else 'idle'}"
        )


# ── CLI ──────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Nagatha's Harvest Curator — ShapeNet to Sigma, one at a time.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Browse the whole collection (Ctrl+C to stop, resumes later)
  python harvest_curator.py /path/to/ShapeNetCore /path/to/output

  # Process just 5 objects
  python harvest_curator.py /path/to/ShapeNetCore /path/to/output --max 5

  # Faster pace (for testing)
  python harvest_curator.py /path/to/ShapeNetCore /path/to/output --fast

  # Check status
  python harvest_curator.py /path/to/ShapeNetCore /path/to/output --status

  # Review flagged objects
  python harvest_curator.py /path/to/ShapeNetCore /path/to/output --flagged
        """
    )

    parser.add_argument("shapenet_dir", help="Path to local ShapeNet directory")
    parser.add_argument("output_dir", help="Where to write Sigma files")
    parser.add_argument("--library", help="Library index directory (default: output_dir)")
    parser.add_argument("--max", type=int, help="Max objects to process this session")
    parser.add_argument("--fast", action="store_true",
                        help="Faster pace (1-5s intervals instead of 2-30s)")
    parser.add_argument("--status", action="store_true",
                        help="Show status and exit")
    parser.add_argument("--flagged", action="store_true",
                        help="List flagged objects for review")
    parser.add_argument("--no-shuffle", action="store_true",
                        help="Process in order instead of random")
    parser.add_argument("--quality", type=float, default=0.70,
                        help="Good-enough threshold (default: 0.70)")

    args = parser.parse_args()

    config = HarvestConfig()
    if args.fast:
        config.MIN_INTERVAL_SECONDS = 1
        config.MAX_INTERVAL_SECONDS = 5
    config.GOOD_ENOUGH = args.quality

    library_dir = args.library or args.output_dir
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(library_dir, exist_ok=True)

    curator = HarvestCurator(
        shapenet_dir=args.shapenet_dir,
        output_dir=args.output_dir,
        library_dir=library_dir,
        config=config
    )

    if args.status:
        print(curator.status())
        return

    if args.flagged:
        flagged = [e for e in curator.log.entries.values()
                  if e.get("decision") == Decision.FLAGGED]
        if flagged:
            print(f"\n  [Nagatha] {len(flagged)} objects flagged for your review:\n")
            for e in flagged:
                print(f"  - {e['file']}")
                print(f"    Quality: {e.get('quality', '?')}, Reason: {e.get('reason', '?')}")
                print()
        else:
            print("  [Nagatha] Nothing flagged. Either everything was clear-cut,")
            print("           or I haven't started yet.")
        return

    try:
        curator.browse(
            max_objects=args.max,
            shuffle=not args.no_shuffle
        )
    except KeyboardInterrupt:
        print(f"\n  [Nagatha] Interrupted. All progress saved. "
              f"Run again to continue where we left off.")


if __name__ == "__main__":
    main()
