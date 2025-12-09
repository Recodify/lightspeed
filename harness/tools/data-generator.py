#!/usr/bin/env python3
import argparse
import csv
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set

from coolname import generate_slug


RECORD_FIELDNAMES = [
    "series_id",
    "series_uuid",
    "series_name",
    "start_date",
    "end_date",
    "ingest_date",
    "reading_type_name",
    "reading_type_id",
    "unit_of_measure",
    "unit_of_mesasure_id",
    "value",
]

READING_TYPE_FIELDS = [
    "reading_type_id",
    "reading_type_name",
    "unit_of_measure",
    "unit_of_mesasure_id",
    "value_min",
    "value_max",
]

DATE_FIELDS: Set[str] = {"start_date", "end_date", "ingest_date"}


READING_TYPES = [
    {
        "reading_type_id": 1,
        "reading_type_name": "Active Energy Import",
        "unit_of_measure": "kWh",
        "unit_of_mesasure_id": 1,
        "value_min": 0.0,
        "value_max": 5.0,
    },
    {
        "reading_type_id": 2,
        "reading_type_name": "Active Power",
        "unit_of_measure": "kW",
        "unit_of_mesasure_id": 2,
        "value_min": 0.0,
        "value_max": 10.0,
    },
    {
        "reading_type_id": 3,
        "reading_type_name": "Voltage",
        "unit_of_measure": "V",
        "unit_of_mesasure_id": 3,
        "value_min": 210.0,
        "value_max": 250.0,
    },
    {
        "reading_type_id": 4,
        "reading_type_name": "Current",
        "unit_of_measure": "A",
        "unit_of_mesasure_id": 4,
        "value_min": 0.0,
        "value_max": 40.0,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate simulated timeseries CSV data."
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output CSV file path.",
    )

    # Only one of record count, size, or (start and end) used to determine record count
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record-count",
        type=int,
        help="Total number of records to generate.",
    )
    group.add_argument(
        "--size-mb",
        type=float,
        help="Approximate target file size in megabytes, used to estimate record count.",
    )
    group.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START_DATE", "END_DATE"),
        help="Start and end ISO datetimes, used with time-between to derive record count.",
    )

    parser.add_argument(
        "--unique-series-count",
        type=int,
        required=True,
        help="Number of distinct series_id values.",
    )
    parser.add_argument(
        "--series-name-length",
        type=int,
        default=24,
        help="Target character length for generated series_name values using coolname words.",
    )

    parser.add_argument(
        "--distribution-type",
        choices=["balanced", "random", "hot"],
        default="balanced",
        help="How records are distributed across series.",
    )

    parser.add_argument(
        "--time-between-seconds",
        type=int,
        default=3600,
        help="Time delta between successive records in the same series in seconds.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility.",
    )

    parser.add_argument(
        "--base-start-date",
        type=str,
        default=None,
        help="Base ISO datetime for generated timestamps if date-range is not used.",
    )
    parser.add_argument(
        "--field-style",
        choices=["snake", "camel"],
        default="snake",
        help="Output column naming style.",
    )
    parser.add_argument(
        "--field",
        dest="fields",
        action="append",
        choices=RECORD_FIELDNAMES,
        help="Canonical field to include in the output. Repeat to choose a subset/order; defaults to all fields.",
    )
    parser.add_argument(
        "--rename-field",
        dest="field_renames",
        action="append",
        default=[],
        metavar="CANONICAL=OUTPUT",
        help="Override an output column name; CANONICAL must be one of the base field names.",
    )

    return parser.parse_args()


def _to_camel_case(value: str) -> str:
    parts = value.split("_")
    if not parts:
        return value
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _parse_field_renames(values: List[str]) -> Dict[str, str]:
    renames: Dict[str, str] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(
                f"Invalid --rename-field '{raw}'. Expected CANONICAL=OUTPUT."
            )
        src, dest = raw.split("=", 1)
        src = src.strip()
        dest = dest.strip()
        if src not in RECORD_FIELDNAMES:
            raise ValueError(
                f"Invalid canonical field '{src}' in rename; must be one of {RECORD_FIELDNAMES}"
            )
        if not dest:
            raise ValueError("Output column name in --rename-field cannot be empty.")
        renames[src] = dest
    return renames


def _resolve_field_order(selected_fields: Optional[List[str]]) -> List[str]:
    if not selected_fields:
        return RECORD_FIELDNAMES
    order: List[str] = []
    seen: Set[str] = set()
    for name in selected_fields:
        if name not in RECORD_FIELDNAMES:
            raise ValueError(
                f"Invalid field '{name}'. Must be one of {RECORD_FIELDNAMES}."
            )
        if name in seen:
            raise ValueError(f"Duplicate field '{name}' in --field list.")
        seen.add(name)
        order.append(name)
    return order


def _build_output_field_map(
    field_order: List[str], style: str, renames: Dict[str, str]
) -> Dict[str, str]:
    output: Dict[str, str] = {}
    used: Set[str] = set()
    for canonical in field_order:
        styled = canonical if style == "snake" else _to_camel_case(canonical)
        output_name = renames.get(canonical, styled)
        if output_name in used:
            raise ValueError(
                f"Output column '{output_name}' defined more than once."
            )
        used.add(output_name)
        output[canonical] = output_name
    return output


def parse_iso_datetime(value: str) -> datetime:
    # Allow Z suffix as UTC
    if value.endswith("Z"):
        value = value[:-1]
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(value)


def estimate_record_count_from_size(target_mb: float) -> int:
    # Very rough average bytes per record, adjust if needed
    avg_bytes_per_record = 150
    target_bytes = int(target_mb * 1024 * 1024)
    count = max(1, target_bytes // avg_bytes_per_record)
    return count


def derive_record_count_from_date_range(
    start: datetime,
    end: datetime,
    time_between: int,
    series_count: int,
) -> int:
    if end <= start:
        raise ValueError("END_DATE must be after START_DATE")
    delta_seconds = (end - start).total_seconds()
    if delta_seconds < 0:
        raise ValueError("Negative date range duration")
    per_series = int(delta_seconds // time_between) + 1
    if per_series <= 0:
        raise ValueError("Time between is larger than date range")
    return per_series * series_count


def allocate_records(
    total_records: int,
    series_count: int,
    distribution_type: str,
) -> List[int]:
    if series_count <= 0:
        raise ValueError("series_count must be positive")
    if total_records < series_count:
        # At least one record per series if we can
        raise ValueError("total_records must be >= series_count")

    if distribution_type == "balanced":
        base = total_records // series_count
        rem = total_records % series_count
        counts = [base] * series_count
        for i in range(rem):
            counts[i] += 1
        return counts

    if distribution_type == "random":
        weights = [random.random() for _ in range(series_count)]
        total_weight = sum(weights)
        raw_counts = [int(total_records * w / total_weight) for w in weights]

        # Ensure at least one per series
        raw_counts = [c if c > 0 else 1 for c in raw_counts]
        current_total = sum(raw_counts)

        # Adjust to exact total
        while current_total > total_records:
            idx = random.randrange(series_count)
            if raw_counts[idx] > 1:
                raw_counts[idx] -= 1
                current_total -= 1
        while current_total < total_records:
            idx = random.randrange(series_count)
            raw_counts[idx] += 1
            current_total += 1
        return raw_counts

    if distribution_type == "hot":
        # Hot series get most of the records, cold series get few
        hot_count = max(1, series_count // 5)
        cold_count = series_count - hot_count

        hot_weight = 0.8
        cold_weight = 0.2

        hot_records = int(total_records * hot_weight)
        cold_records = total_records - hot_records

        # Each hot gets at least 1
        hot_base = max(1, hot_records // hot_count)
        cold_base = 1 if cold_count > 0 else 0

        counts = [0] * series_count
        # Assign base counts
        for i in range(hot_count):
            counts[i] = hot_base
        for i in range(hot_count, series_count):
            counts[i] = cold_base

        current_total = sum(counts)
        # Distribute remaining records, prefer hot series
        hot_indices = list(range(hot_count))
        cold_indices = list(range(hot_count, series_count))

        while current_total < total_records:
            if random.random() < 0.8 and hot_indices:
                idx = random.choice(hot_indices)
            elif cold_indices:
                idx = random.choice(cold_indices)
            else:
                idx = random.randrange(series_count)
            counts[idx] += 1
            current_total += 1

        return counts

    raise ValueError(f"Unknown distribution type {distribution_type}")


def _generate_series_name(target_len: int, seed_value: Optional[int]) -> str:
    """Generate a coolname-based series name close to the target length, deterministically if seeded."""
    if target_len <= 0:
        target_len = 1

    # If a seed is provided, isolate RNG state so other random flows remain unchanged
    state = None
    if seed_value is not None:
        state = random.getstate()
        random.seed(seed_value)

    try:
        words: List[str] = []
        # Keep adding two-word slugs until we reach/exceed the target length
        while len("-".join(words)) < target_len:
            words.extend(generate_slug(2).split("-"))

        name = "-".join(words)
        # Trim if we overshoot the target to keep it close to the requested length
        if len(name) > target_len:
            name = name[:target_len]
            # Avoid trailing hyphen after trim
            if name.endswith("-"):
                name = name.rstrip("-")
        return name
    finally:
        if state is not None:
            random.setstate(state)


def build_series_meta(series_count: int, series_name_length: int, base_seed: Optional[int]) -> List[Dict]:
    meta = []
    for sid in range(1, series_count + 1):
        series_uuid = str(uuid.uuid4())
        # Seed per series so the same series_id gets the same name given a base seed
        per_series_seed = (base_seed or 0) + sid if base_seed is not None else None
        series_name = _generate_series_name(series_name_length, per_series_seed)
        reading_type = random.choice(READING_TYPES)
        # Each series is tied to one reading type and unit
        entry = {
            "series_id": sid,
            "series_uuid": series_uuid,
            "series_name": series_name,
            **{field: reading_type[field] for field in READING_TYPE_FIELDS},
        }
        meta.append(entry)
    return meta


def _build_record(meta: Dict, start_dt: datetime, end_dt: datetime, ingest_dt: datetime, value: float) -> Dict:
    """Map series metadata and timestamps into a record payload."""
    record = {
        "series_id": meta["series_id"],
        "series_uuid": meta["series_uuid"],
        "series_name": meta["series_name"],
        "start_date": start_dt,
        "end_date": end_dt,
        "ingest_date": ingest_dt,
        "value": value,
    }
    record.update(
        {
            "reading_type_name": meta["reading_type_name"],
            "reading_type_id": meta["reading_type_id"],
            "unit_of_measure": meta["unit_of_measure"],
            "unit_of_mesasure_id": meta["unit_of_mesasure_id"],
        }
    )
    return record


def _generate_series_records(
    meta: Dict, count: int, first_start: datetime, per_series_time_between: timedelta
) -> List[Dict]:
    records: List[Dict] = []
    current_start = first_start
    for _ in range(count):
        end_dt = current_start + per_series_time_between
        ingest_dt = end_dt + timedelta(seconds=random.randint(5, 300))
        value = random.uniform(meta["value_min"], meta["value_max"])
        records.append(
            _build_record(
                meta,
                current_start,
                end_dt,
                ingest_dt,
                value,
            )
        )
        current_start = current_start + per_series_time_between
    return records


def generate_records(
    series_meta: List[Dict],
    records_per_series: List[int],
    time_between_seconds: int,
    base_start: Optional[datetime],
    date_range: Optional[Tuple[datetime, datetime]],
) -> List[Dict]:
    records = []

    if date_range is not None:
        start_range, end_range = date_range
        # In this mode we ignore distribution type and regenerate balanced spacing
        # records_per_series list already derived from date range, using balanced assumption
        per_series_time_between = timedelta(seconds=time_between_seconds)
        for meta, count in zip(series_meta, records_per_series):
            records.extend(
                _generate_series_records(
                    meta,
                    count,
                    start_range,
                    per_series_time_between,
                )
            )
        return records

    # No explicit date range, use base_start plus per series offset
    if base_start is None:
        base_start = datetime.utcnow()

    per_series_time_between = timedelta(seconds=time_between_seconds)

    for meta, count in zip(series_meta, records_per_series):
        # Random offset per series so they are not perfectly aligned
        series_offset_seconds = random.randint(0, time_between_seconds * 10)
        first_start = base_start + timedelta(seconds=series_offset_seconds)
        records.extend(
            _generate_series_records(
                meta,
                count,
                first_start,
                per_series_time_between,
            )
        )

    return records


def write_csv(
    output_path: str,
    records: List[Dict],
    field_order: List[str],
    output_field_map: Dict[str, str],
) -> None:
    def _format_value(field: str, value):
        if field in DATE_FIELDS:
            return value.isoformat() + "Z"
        return value

    fieldnames = [output_field_map[field] for field in field_order]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            row = {
                output_field_map[field]: _format_value(field, rec[field])
                for field in field_order
            }
            writer.writerow(row)


def main():
    args = parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    series_count = args.unique_series_count

    date_range = None
    base_start = None

    if args.date_range:
        start_str, end_str = args.date_range
        start_dt = parse_iso_datetime(start_str)
        end_dt = parse_iso_datetime(end_str)
        date_range = (start_dt, end_dt)
        total_records = derive_record_count_from_date_range(
            start_dt,
            end_dt,
            args.time_between_seconds,
            series_count,
        )
        # In date range mode records are balanced
        records_per_series = allocate_records(
            total_records, series_count, "balanced"
        )
    else:
        if args.record_count is not None:
            total_records = args.record_count
        elif args.size_mb is not None:
            total_records = estimate_record_count_from_size(args.size_mb)
        else:
            raise ValueError(
                "One of record-count, size-mb, or date-range must be provided."
            )

        if total_records < series_count:
            raise ValueError(
                "Total record count must be at least unique-series-count."
            )

        records_per_series = allocate_records(
            total_records, series_count, args.distribution_type
        )

        if args.base_start_date:
            base_start = parse_iso_datetime(args.base_start_date)
        else:
            base_start = datetime.utcnow()

    series_meta = build_series_meta(series_count, max(1, args.series_name_length), args.seed)
    records = generate_records(
        series_meta,
        records_per_series,
        args.time_between_seconds,
        base_start,
        date_range,
    )

    field_order = _resolve_field_order(args.fields)
    field_renames = _parse_field_renames(args.field_renames)
    output_field_map = _build_output_field_map(
        field_order, args.field_style, field_renames
    )

    # Shuffle records so series are interleaved
    random.shuffle(records)

    write_csv(args.output, records, field_order, output_field_map)

    print(
        f"Wrote {len(records)} records for {series_count} series to {args.output}"
    )
    print(f"Approx size on disk: {os.path.getsize(args.output) / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
