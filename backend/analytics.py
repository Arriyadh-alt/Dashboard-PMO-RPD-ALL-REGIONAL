"""Explicit populations: source survey rows, consistent unique survey cohorts, master stock.

No source row is changed or deleted. Ambiguous identities/statuses are reported,
not silently resolved. Historical state snapshots are never inferred from today's state.
"""

import calendar
import hashlib
import re
from collections import Counter, defaultdict
from datetime import date, timedelta


FIELDS = ("pam", "ab", "kel", "sv", "mi", "t", "c1", "kf", "fa", "mt", "kd", "mf", "pr", "sc", "tg")
DEFAULT_RULES = {"minimum_sample": 20, "high_backlog_rate": 0.30, "cooling_interest_rate": 0.10}


def ratio(a, b):
    return a / b if b else None


def source_date(value):
    if not value:
        return None
    try:
        value = int(value)
        year = value // 10000
        return date(2000 + year if year < 100 else year, value // 100 % 100, value % 100)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_pam(value):
    value = str(value).strip()
    return value.lstrip("0") if re.fullmatch(r"[0-9]{1,9}", value) and int(value) > 0 else ""


def label(data, field, value):
    values = data.get("dic", {}).get(field, [])
    return str(values[value]) if isinstance(value, int) and 0 <= value < len(values) else ""


def area_key(data, index):
    region, name = str(data['reg'][index]).strip().casefold(), str(data['abs'][index]).strip().casefold()
    return hashlib.sha256(f"{len(region)}:{region}{name}".encode()).hexdigest()[:24]


def case_ref(row):
    identity = f"{row['pam']}|{row['area_key']}|{row['date']}"
    return hashlib.sha256(identity.encode()).hexdigest()[:24]


def prepare(data):
    """Validate column lengths before indexing; keep all original source rows intact."""
    for key in ("months", "abs", "reg", "kels", "svs", "st", "kl", "A", "S", "E", "P", "W", "meta", "dic", "rec"):
        if key not in data:
            raise ValueError(f"Missing data contract field: {key}")
    if not data["months"] or len(data["abs"]) != len(data["reg"]):
        raise ValueError("Invalid month/area data contract")
    area_keys=[area_key(data,index) for index in range(len(data['abs']))]
    if len(set(area_keys))!=len(area_keys):
        raise ValueError('Ambiguous regional/area identities require source reconciliation')
    rec = data["rec"]
    if any(not isinstance(rec.get(key), list) for key in FIELDS):
        raise ValueError("Record columns are missing")
    count = len(rec["pam"])
    if any(len(rec[key]) != count for key in FIELDS):
        raise ValueError("Record column lengths differ")
    rows, locations = [], defaultdict(set)
    for i in range(count):
        row = {key: rec[key][i] for key in FIELDS}
        row.update(index=i, pam=normalize_pam(row["pam"]), date=source_date(row["t"]),
                   fa_date=source_date(row["fa"]), install_date=source_date(row["mt"]))
        row["valid_location"] = all(isinstance(row[key], int) and 0 <= row[key] < len(data[values])
                                    for key, values in (("ab", "abs"), ("kel", "kels"), ("sv", "svs")))
        row["valid"] = bool(row["pam"] and row["date"] and row["valid_location"])
        row["interest"] = label(data, "c1", row["c1"]).strip().casefold() == "berminat"
        row["status"] = label(data, "kf", row["kf"]).strip() or "Tidak tercatat"
        row["installed"] = row["status"].casefold() == "done"
        row["cancelled"] = row["status"].casefold() == "cancel"
        row['area_key'] = area_keys[row['ab']] if isinstance(row['ab'], int) and 0 <= row['ab'] < len(data['abs']) else 'unmapped'
        row["ref"] = case_ref(row)
        if row["valid"]:
            locations[row["pam"]].add((row["ab"], row["kel"]))
        rows.append(row)
    # A PAM ID mapped to several geographies is not assigned arbitrarily to a region.
    ambiguous = {pam for pam, places in locations.items() if len(places) > 1}
    defaults = {}
    for entry in data["S"]:
        if len(entry) >= 4 and 0 <= entry[2] < len(data["kl"]):
            defaults.setdefault(entry[3], data["kl"][entry[2]])
    return {"rows": rows, "ambiguous": ambiguous, "default_coordinators": defaults}


def coordinator(data, prepared, row, overrides):
    name = data["svs"][row["sv"]] if row["valid_location"] else ""
    return overrides.get(name, {}).get("kl") or prepared["default_coordinators"].get(row["sv"], "BELUM TERDAFTAR")


def period_bounds(data, filters):
    start_index, end_index = int(filters.get("m0", 0)), int(filters.get("m1", len(data["months"]) - 1))
    if not 0 <= start_index <= end_index < len(data["months"]):
        raise ValueError("Invalid reporting period")
    start = date.fromisoformat(data["months"][start_index] + "-01") if start_index else None
    year, month = map(int, data["months"][end_index].split("-"))
    end = date(year, month, calendar.monthrange(year, month)[1])
    if filters.get("start"):
        start = date.fromisoformat(filters["start"])
    if filters.get("end"):
        end = date.fromisoformat(filters["end"])
    if start and start > end:
        raise ValueError("Start date follows end date")
    return start, end


def matches(data, prepared, row, filters, overrides, date_field="date", dates=True, bounds=None):
    if not row["valid"]:
        return False
    if filters.get("reg") and data["reg"][row["ab"]] != filters["reg"]:
        return False
    for field in ("ab", "kel"):
        if int(filters.get(field, -1)) >= 0 and row[field] != int(filters[field]):
            return False
    if filters.get("coordinator") and coordinator(data, prepared, row, overrides) != filters["coordinator"]:
        return False
    statuses = filters.get("statuses", [])
    if statuses and row["status"] not in statuses:
        return False
    if dates:
        start, end = bounds if bounds is not None else period_bounds(data, filters)
        value = row[date_field]
        if not value or (start and value < start) or value > end:
            return False
    return True


def scoped_rows(data, prepared, filters, overrides, date_field="date"):
    bounds=period_bounds(data,filters)
    statuses=filters.get('statuses',[])
    base_filters={**filters,'statuses':[]} if statuses else filters
    rows=[row for row in prepared['rows'] if matches(data,prepared,row,base_filters,overrides,date_field,bounds=bounds)]
    return status_scope(rows,statuses)


def status_scope(rows,statuses):
    if not statuses:
        return rows
    states=defaultdict(set)
    for row in rows: states[row['pam']].add((row['interest'],row['status'].casefold()))
    # Keep source rows searchable, but never let a status filter erase their conflict.
    return [{**row,'status_conflict':len(states[row['pam']])>1} for row in rows if row['status'] in statuses]


def cohort(rows, ambiguous):
    grouped = defaultdict(list)
    for row in rows:
        if row["pam"] not in ambiguous:
            grouped[row["pam"]].append(row)
    interested = installed = conflicted = pending = 0
    for records in grouped.values():
        interest_values = {record["interest"] for record in records}
        statuses = {record["status"].casefold() for record in records}
        if len(interest_values) > 1 or len(statuses) > 1 or any(record.get('status_conflict') for record in records):
            conflicted += 1
            continue
        interested += int(records[0]["interest"])
        installed += int(records[0]["interest"] and records[0]["installed"])
        pending += int(records[0]['interest'] and not records[0]['installed'] and not records[0]['cancelled'])
    return {"canvassed": len(grouped), "interested": interested, "installed": installed,
            "interest_rate": ratio(interested, len(grouped)), "installation_rate": ratio(installed, interested),
            "conflicted_status_customers": conflicted,
            "excluded_geography_customers": len({row["pam"] for row in rows if row["pam"] in ambiguous}),
            "survey_rows": len(rows), 'pending_customers':pending}


def master_stock(data, filters):
    selected = [row for row in data["P"] if
                (not filters.get("reg") or data["reg"][row[0]] == filters["reg"])
                and (int(filters.get("ab", -1)) < 0 or row[0] == int(filters["ab"]))
                and (int(filters.get("kel", -1)) < 0 or row[1] == int(filters["kel"]))]
    potential = sum(row[2] for row in selected)
    matched = sum(row[3] for row in selected)
    return {"potential": potential, "matched_interested": matched, "remaining": potential - matched,
            "installed": sum(row[4] for row in selected),
            "scope": "Master snapshot: seluruh periode; regional/area/kelurahan saja. Tidak mengikuti filter tim/status/tanggal."}


def previous_period(data, prepared, filters):
    start, end = period_bounds(data, filters)
    if not start:
        return None
    if filters.get("start") or filters.get("end"):
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - (end - start)
    else:
        months = int(filters.get("m1", len(data["months"]) - 1)) - int(filters.get("m0", 0)) + 1
        serial = start.year * 12 + start.month - 1 - months
        previous_start = date(serial // 12, serial % 12 + 1, 1)
        previous_end = start - timedelta(days=1)
    known_dates = [row["date"] for row in prepared["rows"] if row['valid']]
    if not known_dates:
        return None
    coverage_start,coverage_end=min(known_dates),max(known_dates)
    def declared_date(name):
        value=data['meta'].get(name)
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return source_date(value)
    declared_start,declared_end=declared_date('tmin'),declared_date('tmax')
    if declared_start: coverage_start=max(coverage_start,declared_start)
    if declared_end: coverage_end=min(coverage_end,declared_end)
    if previous_start < coverage_start or previous_end > coverage_end:
        return None
    return {**filters, "start": previous_start.isoformat(), "end": previous_end.isoformat()}


def quality(data, prepared):
    rows = prepared["rows"]
    identifiers = [row["pam"] for row in rows if row["pam"]]
    counts = Counter(identifiers)
    duplicate_groups = sum(value > 1 for value in counts.values())
    return {"imported_records": len(rows), "valid_records": sum(row["valid"] for row in rows),
            "invalid_pam": sum(not row["pam"] for row in rows),
            "missing_mandatory": sum(not row["date"] or not row["valid_location"] or not row["pam"] for row in rows),
            "unmatched_mapping": sum(not row["valid_location"] for row in rows),
            "duplicate_records": sum(value - 1 for value in counts.values()), "duplicate_customers": duplicate_groups,
            "ambiguous_geography_customers": len(prepared["ambiguous"]),
            "invalid_survey_dates": sum(not row["date"] for row in rows),
            "unknown_installation_status": sum(row["status"] == "Tidak tercatat" for row in rows),
            "source_sync": data["meta"].get("sync", {}),
            "snapshot_comparison": "Insufficient Data: historical state snapshots are not provided."}


def priority(metrics, context, rules):
    if context.get("supply") == "constrained":
        return "Requires Supply Improvement", "Supply terkonfirmasi terbatas; verifikasi perbaikan sebelum penambahan canvassing. Bukti rinci hanya tersedia untuk administrator."
    if context.get("supply") != "ready" or context.get("readiness") != "ready":
        return "Insufficient Data", "Supply dan kesiapan pemasangan belum dikonfirmasi; bukan rekomendasi canvassing."
    if metrics["canvassed"] < rules["minimum_sample"]:
        return "Insufficient Data", "Sampel pelanggan di bawah batas minimum."
    backlog = metrics['pending_customers']
    if (metrics["interest_rate"] or 0) < rules["cooling_interest_rate"]:
        return "Cooling Down", "Konversi minat di bawah ambang; tinjau kondisi area terlebih dahulu."
    if (ratio(backlog, metrics["interested"]) or 0) >= rules["high_backlog_rate"]:
        return "High Priority", "Prioritaskan verifikasi backlog; tidak berarti area siap canvassing baru."
    return ("Medium Priority" if backlog else "Low Priority"), "Tindak lanjut proporsional terhadap backlog kohort; kondisi area telah dikonfirmasi."


def build_analysis(data, prepared, filters, store, role):
    overrides = store.latest("mapping").get("all", {})
    rows = scoped_rows(data, prepared, filters, overrides)
    metrics = cohort(rows, prepared["ambiguous"])
    stock = master_stock(data, filters)
    prior_filters = previous_period(data, prepared, filters)
    previous = cohort(scoped_rows(data, prepared, prior_filters, overrides), prepared["ambiguous"]) if prior_filters else None
    regions, areas, teams = [], [], []
    rules = {**DEFAULT_RULES, **store.latest("rules").get("all", {})}
    contexts = store.latest("area_context")
    by_area,by_region=defaultdict(list),defaultdict(list)
    for row in rows:
        by_area[row['ab']].append(row)
        by_region[data['reg'][row['ab']]].append(row)
    for kind, destinations, values in (("region", regions, sorted(set(data["reg"]))),
                                        ("area", areas, range(len(data["abs"])))):
        for value in values:
            if kind == "region" and filters.get("reg") and value != filters["reg"]:
                continue
            if kind == "area" and ((filters.get("reg") and data["reg"][value] != filters["reg"])
                                   or (int(filters.get("ab", -1)) >= 0 and value != int(filters["ab"]))):
                continue
            subset=(by_region if kind=='region' else by_area).get(value,[])
            group_filters = {**filters, **({"reg": value} if kind == "region" else {"ab": value})}
            group = cohort(subset, prepared["ambiguous"])
            group_stock = master_stock(data, group_filters)
            if not subset and not group_stock["potential"]:
                continue
            entry = {"name": value if kind == "region" else data["abs"][value], "key": value,
                     **group, **{"potential": group_stock["potential"], "remaining": group_stock["remaining"]},
                     "contribution": ratio(group["installed"], metrics["installed"]),
                     "pending": sum(row["interest"] and not row["installed"] and not row["cancelled"] for row in subset),
                     "last_activity": max(row["date"] for row in subset).isoformat() if subset else None,
                     "obstacles": dict(Counter(label(data, "kd", row["kd"]) for row in subset if label(data, "kd", row["kd"])))}
            if kind == "area":
                entry["priority"], entry["reason"] = priority(group, contexts.get(area_key(data, value), {}), rules)
                entry["regional"] = data["reg"][value]
            destinations.append(entry)
    grouped_teams = defaultdict(list)
    for row in rows:
        grouped_teams[coordinator(data, prepared, row, overrides)].append(row)
    for name, records in grouped_teams.items():
        group = cohort(records, prepared["ambiguous"])
        activity_days = len({(row["sv"], row["date"]) for row in records})
        surveyors = {row["sv"] for row in records}
        entry = {"name": name, **group, "surveyors_with_activity": len(surveyors),
                 "active_surveyors": sum(overrides.get(data["svs"][sv], {}).get("st", data["st"][sv]) == 0 for sv in surveyors),
                 "observed_surveyor_days": activity_days, "interested_per_observed_day": ratio(group["interested"], activity_days)}
        if role == "owner":
            by_surveyor=defaultdict(list)
            for row in records: by_surveyor[row['sv']].append(row)
            entry["individuals"] = [{"name": data["svs"][sv], **cohort(by_surveyor[sv], prepared["ambiguous"])} for sv in sorted(surveyors)]
        teams.append(entry)
    trends = defaultdict(list)
    install_events = defaultdict(set)
    trend_rows=scoped_rows(data,prepared,{**filters,'statuses':[]},overrides)
    for row in trend_rows:
        trends[row["date"].strftime("%Y-%m")].append(row)
    # Installation events use installation date, not survey month or today's status history.
    for row in scoped_rows(data, prepared, filters, overrides, "install_date"):
        if row["installed"] and row["pam"] not in prepared["ambiguous"]:
            install_events[row["install_date"].strftime("%Y-%m")].add(row["pam"])
    timeline = [{"month": key, **cohort(status_scope(trends.get(key, []),filters.get('statuses',[])), prepared["ambiguous"]),
                 "installation_events": len(install_events.get(key, set()))} for key in sorted(set(trends) | set(install_events))]
    trend_series = {"monthly": timeline}
    for granularity in ("daily", "weekly"):
        grouped, installed_events = defaultdict(list), defaultdict(set)
        def bucket(value):
            if granularity == "daily":
                return value.isoformat()
            year, week, _ = value.isocalendar()
            return f"{year}-W{week:02d}"
        for row in trend_rows:
            grouped[bucket(row["date"])].append(row)
        for row in scoped_rows(data, prepared, filters, overrides, "install_date"):
            if row["installed"] and row["pam"] not in prepared["ambiguous"]:
                installed_events[bucket(row["install_date"])].add(row["pam"])
        trend_series[granularity] = [{"month": key, **cohort(status_scope(grouped.get(key, []),filters.get('statuses',[])), prepared["ambiguous"]),
                                      "installation_events": len(installed_events.get(key, set()))}
                                     for key in sorted(set(grouped) | set(installed_events))]
    pending = [row for row in rows if row["interest"] and not row["installed"] and not row["cancelled"]]
    latest_actions = store.latest("followup")
    aging = Counter({key: 0 for key in ("0–3", "4–7", "8–14", "15–30", ">30", "Insufficient Data")})
    unique_pending = {row["ref"]: row for row in pending}
    today = date.today()
    resolved_manually = 0
    urgent = []
    for ref in unique_pending:
        action = latest_actions.get(ref, {})
        if action.get("status", "").casefold() in ("done", "cancel"):
            resolved_manually += 1
            continue
        if action.get("target_date") and date.fromisoformat(action["target_date"]) < today:
            urgent.append({"ref": ref, "pic": action.get("pic", ""), "target_date": action["target_date"]})
        if not action.get("case_started"):
            aging["Insufficient Data"] += 1
        else:
            days = max(0, (today - date.fromisoformat(action["case_started"])).days - action.get("pause_days", 0))
            aging["0–3" if days <= 3 else "4–7" if days <= 7 else "8–14" if days <= 14 else "15–30" if days <= 30 else ">30"] += 1
    insights = []
    eligible = [region for region in regions if region['canvassed'] >= rules['minimum_sample'] and region["interested"] and region["installation_rate"] is not None]
    for region in eligible:
        if metrics["installation_rate"] is not None and region["installation_rate"] < metrics["installation_rate"]:
            insights.append({"severity": "High", "area": region["name"], "metric": region["installation_rate"],
                             "baseline": metrics["installation_rate"], "unit": "installation_rate",
                             "action": "Tinjau status kasus dan hambatan pemasangan sebelum menambah canvassing."})
    if not insights:
        insights.append({"severity": "Info", "area": "Cakupan terpilih", "metric": len(pending), "baseline": len(rows),
                         "unit": "pending_survey_rows", "action": "Verifikasi PIC serta kesiapan pemasangan untuk baris berminat yang belum Done/Cancel." if rows else "Insufficient Data: tidak ada aktivitas survei valid dalam cakupan terpilih."})
    target = target_analysis(data, prepared, filters, store, overrides)
    return {"metrics": metrics, "master": stock, "previous": previous,
            "previous_scope": {"start": prior_filters["start"], "end": prior_filters["end"]} if prior_filters else None,
            "regions": regions, "areas": areas, "teams": teams, "trends": timeline, "trend_series": trend_series,
            "target": target, "insights": insights, "rules": rules,
            "outstanding": {"survey_rows": len(pending), "case_references": len(unique_pending),
                            "manually_resolved": resolved_manually, "active_references": len(unique_pending) - resolved_manually,
                            "urgent_count": len(urgent), "urgent": urgent if role == "owner" else [],
                            "by_status": dict(Counter(row["status"] for row in pending)),
                            "by_region": dict(Counter(data["reg"][row["ab"]] for row in pending)), "aging": dict(aging),
                            "aging_as_of": today.isoformat(), "aging_rule": "Hari kalender sejak tanggal awal kasus terkonfirmasi administrator, dikurangi total hari jeda terkonfirmasi. Tidak memakai tanggal survei."},
            "scope": {"start": period_bounds(data, filters)[0].isoformat() if period_bounds(data, filters)[0] else None,
                      "end": period_bounds(data, filters)[1].isoformat(),
                      "filters": filters, "cohort": "PAM ID unik dalam kohort tanggal survei; konflik geografis dikecualikan, konflik status tidak diasumsikan selesai.",
                      "history": "Perbandingan kohort tanggal survei dengan status pada impor saat ini; bukan snapshot status historis."}}


def target_ref(month, region, area, data):
    return f"{month}|{region}|{area_key(data, area) if area >= 0 else 'all'}"


def target_analysis(data, prepared, filters, store, overrides):
    unavailable = {"available": False, "reason": "Insufficient Data: target bulanan sebanding belum dikonfigurasi."}
    if filters.get("coordinator") or filters.get("statuses") or int(filters.get("kel", -1)) >= 0 or filters.get("start") or filters.get("end"):
        return {**unavailable, "reason": "Insufficient Data: target hanya untuk bulan penuh dan cakupan regional/area yang sama."}
    months = data["months"][int(filters.get("m0", 0)):int(filters.get("m1", len(data["months"]) - 1)) + 1]
    targets = store.latest("target")
    entries = [targets.get(target_ref(month, filters.get("reg", ""), int(filters.get("ab", -1)), data)) for month in months]
    if not all(entries):
        return unavailable
    total = sum(entry["target"] for entry in entries)
    # The first survey bucket may include earlier months; targets never use that open lower bound.
    event_filters = {**filters, "start": months[0] + "-01"}
    events = scoped_rows(data, prepared, event_filters, overrides, "install_date")
    actual = len({row["pam"] for row in events if row["installed"] and row["pam"] not in prepared["ambiguous"]})
    return {"available": True, "target": total, "actual": actual, "achievement": ratio(actual, total),
            "remaining": max(0, total - actual), "required_daily": None,
            "reason": "Aktual: PAM unik Done menurut tanggal pemasangan. Estimasi harian tidak tersedia tanpa kalender kerja terverifikasi."}


def record_view(data, prepared, row, overrides, action=None):
    width = 8 if data["reg"][row["ab"]] in ("Timur", "Utara") else 9
    return {"ref": row["ref"], "pam": row["pam"].zfill(width), "survey_date": row["date"].isoformat(),
            "regional": data["reg"][row["ab"]], "area": data["abs"][row["ab"]], "kelurahan": data["kels"][row["kel"]],
            "surveyor": data["svs"][row["sv"]], "coordinator": coordinator(data, prepared, row, overrides),
            "canvassing": label(data, "c1", row["c1"]), "status": row["status"],
            "fa_date": row["fa_date"].isoformat() if row["fa_date"] else None,
            "installation_date": row["install_date"].isoformat() if row["install_date"] else None,
            "obstacle": label(data, "kd", row["kd"]), "master_flag": label(data, "mf", row["mf"]),
            "potential_status": label(data, "pr", row["pr"]), "customer_status": label(data, "sc", row["sc"]),
            "arrears": row["tg"], "followup": action}
