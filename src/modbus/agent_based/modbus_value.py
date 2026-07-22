#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check plugin for the generic Modbus special agent (agent_modbus).

Parses the `<<<modbus_value>>>` agent section, discovers one Checkmk
service per configured register, and renders its value - optionally
scaled to a configurable number of decimal places - as both a text
Result and a graphable Metric.

Agent section format (one line per configured register, emitted by the
compiled agent_modbus binary, see ../libexec/agent_modbus):

    <<<modbus_value>>>
    <cid> <raw_value> <ctype> <name>
    26 100 counter ID1_Bateria-Core
    28 2419 counter ID1_Temperatura-Core
    29 3538 counter ID1_Umidade-Core

Where:
    cid       Register ID configured in the "Check Modbus devices" rule.
    raw_value Raw integer read from the Modbus register (no scaling).
    ctype     "counter" or "gauge" - consumed by agent_modbus itself for
              its own sampling logic; not used by this check.
    name      Register Name configured in the rule - must be unique
              across every rule/slave targeting the same host. This is
              also the Checkmk service item.

Decimal scaling: raw_value is a plain integer with no decimal point,
even though the real-world reading usually has implied decimals (e.g.
2419 -> 24.19 degrees). There is no way to carry a divisor through
agent_modbus itself (it is a precompiled third-party binary with a
fixed 4-field output format), so scaling is applied entirely on this
side, via the "Modbus register value scaling" check parameter rule
(see ../rulesets/modbus_value_params.py), matched per-item. A register
with no matching rule keeps the previous (unscaled, integer) behavior.

Signed values and units: for the same reason as decimal scaling,
neither is carried through agent_modbus - raw_value always arrives as
a plain non-negative integer, and with no unit attached. Both are
therefore also configured per-item via the same "Modbus register
value scaling" rule: "signed" applies 16-bit two's complement to the
raw value before scaling (e.g. a temperature register that can read
below zero), and "unit" is a free-form suffix appended after the
scaled value (e.g. "%" or " °C").

Fixes applied in version 1.1 (2026-07-21):
  - BUGFIX: parse_modbus() used to key the parsed section by `cid`
    alone. When several "Check Modbus devices" rules target the same
    host (one rule per Modbus slave, each reusing the same Register
    IDs but a different Register Name per slave/location), lines from
    different slaves sharing a `cid` were overwriting each other, so
    only as many services were discovered as there were *distinct*
    cids - not one per configured register. Keying by `name` instead
    (already guaranteed unique per rule) fixes this: every configured
    register across every slave now gets its own service.
  - FEATURE: added configurable decimal-place scaling and Metric
    emission (previously the check produced no performance data at
    all, so sensor values could not be graphed).

Features added in version 1.2 (2026-07-22):
  - FEATURE: added a configurable "unit" suffix (e.g. "%", " °C"),
    shown alongside the scaled value in the service summary.
  - BUGFIX/FEATURE: added a configurable "signed" flag so 16-bit
    registers that can read negative (e.g. temperature) are decoded
    via two's complement before scaling, instead of always being
    treated as unsigned.

Features added in version 1.3 (2026-07-22):
  - FEATURE: added configurable "levels_upper"/"levels_lower" WARN/CRIT
    thresholds (see ../rulesets/modbus_value_params.py), applied to the
    scaled value independently in each direction. Previously the check
    always returned OK regardless of the value read.

Changed in version 1.4 (2026-07-22):
  - REFACTOR: the WARN/CRIT comparison is now delegated to the
    documented cmk.agent_based.v2.check_levels() helper (the standard
    Checkmk way to evaluate a value against a "levels_upper"/
    "levels_lower" param), instead of a hand-rolled comparison. Confirmed
    live against the real API on a Checkmk 2.4.0p18 site. Two small
    visible differences from the 1.3 hand-rolled version, both coming
    from check_levels() itself rather than a choice made here:
      * the "(warn/crit ...)" text now appears *before* the "(<cid>)"
        suffix instead of after it, e.g. "Current : 32.00 °C (warn/crit
        at 30.00 °C/35.00 °C) (28)".
      * check_levels() phrases a breach differently per direction -
        "(warn/crit at W/C)" for an upper breach, "(warn/crit below
        W/C)" for a lower one (the 1.3 code always said "at"). The
        OK-with-no-levels case (the vast majority of services) is
        unchanged: "Current : 24.19 °C (28)".

Original author (through v1.0.2): wellingtonsilva67@gmail.com
Adapted and maintained since v1.0.3 by Felipe Soares <felipe.staypuff@gmail.com>
(https://github.com/felipesoaresti/)
Version: 1.4 - 20260722
"""

import re

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    Metric,
    Result,
    Service,
    State,
    check_levels,
)

# Shape of the "levels_upper"/"levels_lower" params, as produced by the
# SimpleLevels form spec: either no levels configured, or a (warn, crit)
# pair to compare the scaled value against.
_NO_LEVELS = ("no_levels", None)

# Column order of each data line under <<<modbus_value>>>, as printed by
# agent_modbus ("%d %d %s %s" -> cid, raw value, ctype, name).
_COLUMN_NAMES = ["cid", "values", "ctype", "name"]


def parse_modbus(string_table):
    """Turn raw agent lines into a dict keyed by Register Name.

    Keying by name (rather than by `cid`) is what allows several
    "Check Modbus devices" rules - each targeting a different Modbus
    slave but reusing the same Register IDs - to coexist on a single
    Checkmk host without one slave's readings overwriting another's.
    """
    parsed = {}
    for line in string_table:
        row = dict(zip(_COLUMN_NAMES, line))
        parsed[row["name"]] = row
    return parsed


agent_section_modbus = AgentSection(
    name="modbus_value",
    parse_function=parse_modbus,
)


def discover_modbus(section):
    """One service per register/name found in the parsed section."""
    for name in section:
        yield Service(item=name)


def _metric_name(item: str) -> str:
    """Sanitize a Register Name into a valid Checkmk metric name.

    Metric names are restricted to lowercase letters, digits and
    underscores, and must start with a letter - Register Names are
    free-form text (e.g. "ID1_Temperatura-Core"), so they need cleanup
    before being used as a metric identifier.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", item).lower()
    if not sanitized or not sanitized[0].isalpha():
        sanitized = f"m_{sanitized}"
    return sanitized


def check_modbus(item, params, section):
    """Render the current value of `item`, scaled per configured decimal places.

    `params` comes from the "Modbus register value scaling" rule
    (check_ruleset_name="modbus_value_params" below), matched by item.
    When no rule matches, `check_default_parameters` below supplies
    decimal_places=0, unit="", signed=False and no levels in either
    direction, which reproduces the original (unscaled, unsigned,
    unitless, always-OK integer) display.
    """
    data = section.get(item)
    if data is None:
        yield Result(state=State.UNKNOWN, summary=f"Not found value for {item}")
        return

    cid = data.get("cid")
    raw_value = data.get("values")
    decimal_places = params.get("decimal_places", 0)
    unit = params.get("unit", "")
    signed = params.get("signed", False)

    try:
        int_value = int(raw_value)
        # 16-bit two's complement: only meaningful for one-word
        # registers, which is what "signed" is documented to support
        # (the agent section does not carry the configured word count).
        if signed and 32768 <= int_value <= 65535:
            int_value -= 65536
        scaled_value = int_value / (10 ** decimal_places)
    except (TypeError, ValueError):
        yield Result(
            state=State.UNKNOWN,
            summary=f"Invalid value '{raw_value}' for {item} ({cid})",
        )
        return

    # Delegate the WARN/CRIT comparison to the documented Checkmk helper
    # (designed to consume exactly the ("no_levels", None) / ("fixed",
    # (warn, crit)) shape that SimpleLevels produces). With label=None it
    # renders as just "<value><unit>", optionally followed by "(warn/crit
    # at ...)" for an upper breach or "(warn/crit below ...)" for a lower
    # one - we then wrap that in this plugin's own "Current : ... (<cid>)"
    # format. check_levels() only ever attaches levels_upper (if "fixed")
    # to the Metric it yields - a lower-only threshold is reflected in the
    # service state/summary correctly, but never shades a band on the
    # graph; this is a limitation of the helper itself, not a choice made
    # here.
    parts = list(
        check_levels(
            scaled_value,
            levels_upper=params.get("levels_upper", _NO_LEVELS),
            levels_lower=params.get("levels_lower", _NO_LEVELS),
            metric_name=_metric_name(item),
            render_func=lambda v: f"{v:.{decimal_places}f}{unit}",
        )
    )
    result = next(p for p in parts if isinstance(p, Result))
    metric = next(p for p in parts if isinstance(p, Metric))

    yield Result(state=result.state, summary=f"Current : {result.summary} ({cid})")
    # Emitted unconditionally (even with decimal_places=0) so every
    # sensor is graphable/available for historical data from day one.
    yield metric


check_plugin_modbus = CheckPlugin(
    name="modbus",
    sections=["modbus_value"],
    service_name="Modbus: %s",
    discovery_function=discover_modbus,
    check_function=check_modbus,
    check_ruleset_name="modbus_value_params",
    check_default_parameters={
        "decimal_places": 0,
        "unit": "",
        "signed": False,
        "levels_upper": _NO_LEVELS,
        "levels_lower": _NO_LEVELS,
    },
)
