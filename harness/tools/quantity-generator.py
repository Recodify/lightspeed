#!/usr/bin/env python3
import argparse
import csv
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from coolname import generate_slug


FIELDNAMES = [
    "id",
    "name",
    "uuid_id",
    "as_of",
    "timestamp",
    "period_start",
    "period_end",
    "published_date",
    "quantity",
]

DATE_FIELDS = {"as_of", "timestamp", "period_start", "period_end", "published_date"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate simulated quantity records in CSV format."
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output CSV file path.",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "parquet"],
        default="csv",
        help="Output file format.",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record-count",
        type=int,
        help="Total number of records to generate.",
    )
    group.add_argument(
        "--size-mb",
        type=float,
        help="Approximate target file size in megabytes; used to estimate record count.",
    )
    group.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help="Start and end ISO datetimes; combined with --time-between-seconds to derive record count.",
    )

    parser.add_argument(
        "--unique-entity-count",
        type=int,
        required=True,
        help="Number of distinct id/name pairs.",
    )
    parser.add_argument(
        "--distribution-type",
        choices=["balanced", "random", "hot"],
        default="balanced",
        help="How records are distributed across entities.",
    )
    parser.add_argument(
        "--time-between-seconds",
        type=int,
        default=3600,
        help="Time delta between successive records in seconds.",
    )
    parser.add_argument(
        "--base-start-date",
        type=str,
        default=None,
        help="Base ISO datetime for generated timestamps when date-range is not used.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--name-length",
        type=int,
        default=20,
        help="Approximate character length for generated names.",
    )
    parser.add_argument(
        "--quantity-min",
        type=float,
        default=0.0,
        help="Minimum quantity value.",
    )
    parser.add_argument(
        "--quantity-max",
        type=float,
        default=100.0,
        help="Maximum quantity value.",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Print progress updates to stderr while generating/writing.",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=100000,
        help="How many records between progress updates when --progress is set.",
    )

    return parser.parse_args()


def parse_iso_datetime(value: str) -> datetime:
    # Allow trailing Z as UTC shorthand
    if value.endswith("Z"):
        value = value[:-1]
    return datetime.fromisoformat(value)


def estimate_record_count_from_size(target_mb: float) -> int:
    avg_bytes_per_record = 120  # rough heuristic
    target_bytes = int(target_mb * 1024 * 1024)
    return max(1, target_bytes // avg_bytes_per_record)


def derive_record_count_from_date_range(
    start: datetime, end: datetime, time_between: int, entity_count: int
) -> int:
    if end <= start:
        raise ValueError("END_DATE must be after START_DATE")
    delta_seconds = (end - start).total_seconds()
    per_entity = int(delta_seconds // time_between) + 1
    if per_entity <= 0:
        raise ValueError("Time between is larger than date range")
    return per_entity * entity_count


def allocate_records(
    total_records: int, entity_count: int, distribution_type: str
) -> List[int]:
    if entity_count <= 0:
        raise ValueError("entity_count must be positive")
    if total_records < entity_count:
        raise ValueError("total_records must be >= entity_count")

    if distribution_type == "balanced":
        base = total_records // entity_count
        rem = total_records % entity_count
        counts = [base] * entity_count
        for i in range(rem):
            counts[i] += 1
        return counts

    if distribution_type == "random":
        weights = [random.random() for _ in range(entity_count)]
        total_weight = sum(weights)
        raw_counts = [int(total_records * w / total_weight) for w in weights]
        raw_counts = [c if c > 0 else 1 for c in raw_counts]
        current_total = sum(raw_counts)
        while current_total > total_records:
            idx = random.randrange(entity_count)
            if raw_counts[idx] > 1:
                raw_counts[idx] -= 1
                current_total -= 1
        while current_total < total_records:
            idx = random.randrange(entity_count)
            raw_counts[idx] += 1
            current_total += 1
        return raw_counts

    if distribution_type == "hot":
        hot_count = max(1, entity_count // 5)
        cold_count = entity_count - hot_count
        hot_weight = 0.8
        hot_records = int(total_records * hot_weight)
        cold_records = total_records - hot_records
        hot_base = max(1, hot_records // hot_count)
        cold_base = 1 if cold_count > 0 else 0
        counts = [0] * entity_count
        for i in range(hot_count):
            counts[i] = hot_base
        for i in range(hot_count, entity_count):
            counts[i] = cold_base
        current_total = sum(counts)
        hot_indices = list(range(hot_count))
        cold_indices = list(range(hot_count, entity_count))
        while current_total < total_records:
            if random.random() < 0.8 and hot_indices:
                idx = random.choice(hot_indices)
            elif cold_indices:
                idx = random.choice(cold_indices)
            else:
                idx = random.randrange(entity_count)
            counts[idx] += 1
            current_total += 1
        return counts

    raise ValueError(f"Unknown distribution type {distribution_type}")


def _generate_name(target_len: int, seed_value: Optional[int]) -> str:
    state = None
    if seed_value is not None:
        state = random.getstate()
        random.seed(seed_value)
    try:
        words: List[str] = []
        
        while len(".".join(words)) < target_len:
            words.extend(generate_slug(2).split("-"))
        name = ".".join(words)
        if len(name) > target_len:
            name = name[:target_len]
            if name.endswith("."):
                name = name.rstrip(".")
        return f"EDFT.{name.upper()}.EDFT"
    finally:
        if state is not None:
            random.setstate(state)


def build_entity_meta(
    entity_count: int, name_length: int, base_seed: Optional[int]
) -> List[Dict]:
    meta: List[Dict] = []
    for eid in range(1, entity_count + 1):
        per_entity_seed = (base_seed or 0) + eid if base_seed is not None else None
        name = _generate_name(name_length, per_entity_seed)
        meta.append({"id": eid, "name": name, "uuid_id": str(uuid.uuid4())})
    return meta


class ProgressTracker:
    def __init__(self, total: int, interval: int, label: str):
        self.total = max(1, total)
        self.interval = max(1, interval)
        self.label = label
        self.count = 0

    def tick(self, step: int = 1):
        self.count += step
        if self.count % self.interval == 0 or self.count >= self.total:
            self.report()

    def report(self):
        print(
            f"{self.label}: {self.count}/{self.total} ({(self.count / self.total) * 100:.1f}%)",
            file=sys.stderr,
        )


def _build_record(
    meta: Dict,
    period_start: datetime,
    period_end: datetime,
    published: datetime,
    quantity: float,
) -> Dict:
    return {
        "id": meta["id"],
        "name": meta["name"],
        "uuid_id": meta["uuid_id"],
        "as_of_datetime": period_end,
        "timestamp": period_end,
        "period_start": period_start,
        "period_end": period_end,
        "published_date": published,
        "quantity": quantity,
    }


def _generate_entity_records(
    meta: Dict,
    count: int,
    first_start: datetime,
    step: timedelta,
    quantity_min: float,
    quantity_max: float,
) -> List[Dict]:
    records: List[Dict] = []
    current_start = first_start
    for _ in range(count):
        period_start = current_start
        period_end = period_start + step
        published = period_end + timedelta(seconds=random.randint(5, 300))
        quantity = random.uniform(quantity_min, quantity_max)
        records.append(
            _build_record(
                meta,
                period_start,
                period_end,
                published,
                quantity,
            )
        )
        current_start = current_start + step
    return records


def generate_records(
    meta: List[Dict],
    records_per_entity: List[int],
    time_between_seconds: int,
    base_start: Optional[datetime],
    date_range: Optional[Tuple[datetime, datetime]],
    quantity_min: float,
    quantity_max: float,
    progress: Optional[ProgressTracker],
) -> List[dict]:
    records: List[dict] = []
    step = timedelta(seconds=time_between_seconds)

    if date_range is not None:
        start_range, _ = date_range
        for m, count in zip(meta, records_per_entity):
            generated = _generate_entity_records(
                m,
                count,
                start_range,
                step,
                quantity_min,
                quantity_max,
            )
            records.extend(generated)
            if progress:
                progress.tick(len(generated))
        return records

    if base_start is None:
        base_start = datetime.utcnow()

    for m, count in zip(meta, records_per_entity):
        offset_seconds = random.randint(0, time_between_seconds * 10)
        first_start = base_start + timedelta(seconds=offset_seconds)
        generated = _generate_entity_records(
            m,
            count,
            first_start,
            step,
            quantity_min,
            quantity_max,
        )
        records.extend(generated)
        if progress:
            progress.tick(len(generated))

    return records


def write_csv(
    output_path: str,
    records: List[dict],
    progress: Optional[ProgressTracker],
) -> None:
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    key: rec[key].isoformat() + "Z"
                    if key in DATE_FIELDS
                    else rec[key]
                    for key in FIELDNAMES
                }
            )
            if progress:
                progress.tick()


def write_parquet(output_path: str, records: List[dict]) -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "Parquet output requires pandas (and a parquet engine such as pyarrow or fastparquet)."
        ) from exc

    df = pd.DataFrame(records, columns=FIELDNAMES)
    for field in DATE_FIELDS:
        if field in df.columns:
            df[field] = pd.to_datetime(df[field], utc=True)
    df.to_parquet(output_path, index=False)


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    entity_count = args.unique_entity_count

    if args.record_count is not None:
        record_count = args.record_count
    elif args.size_mb is not None:
        record_count = estimate_record_count_from_size(args.size_mb)
    else:
        start_str, end_str = args.date_range
        start_dt = parse_iso_datetime(start_str)
        end_dt = parse_iso_datetime(end_str)
        record_count = derive_record_count_from_date_range(
            start_dt, end_dt, args.time_between_seconds, entity_count
        )

    if record_count < entity_count:
        raise ValueError(
            "Total record count must be at least the unique-entity-count."
        )

    records_per_entity = allocate_records(
        record_count, entity_count, args.distribution_type
    )

    date_range: Optional[Tuple[datetime, datetime]] = None
    base_start: Optional[datetime] = None
    if args.date_range:
        start_dt = parse_iso_datetime(args.date_range[0])
        end_dt = parse_iso_datetime(args.date_range[1])
        date_range = (start_dt, end_dt)
    elif args.base_start_date:
        base_start = parse_iso_datetime(args.base_start_date)

    meta = build_entity_meta(entity_count, max(1, args.name_length), args.seed)
    gen_progress = (
        ProgressTracker(record_count, args.progress_interval, "Generated")
        if args.progress
        else None
    )
    records = generate_records(
        meta,
        records_per_entity,
        args.time_between_seconds,
        base_start,
        date_range,
        args.quantity_min,
        args.quantity_max,
        gen_progress,
    )

    if gen_progress:
        gen_progress.report()

    random.shuffle(records)
    if args.format == "csv":
        write_progress = (
            ProgressTracker(len(records), args.progress_interval, "Wrote")
            if args.progress
            else None
        )
        write_csv(args.output, records, write_progress)
        if write_progress:
            write_progress.report()
    else:
        write_parquet(args.output, records)

    print(f"Wrote {len(records)} records to {args.output}")
    print(f"Approx size on disk: {os.path.getsize(args.output) / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
