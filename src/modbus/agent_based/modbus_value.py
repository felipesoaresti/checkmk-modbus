#!/usr/bin/env python3
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

Original author (through v1.0.2): wellingtonsilva67@gmail.com
Adapted and maintained since v1.0.3 by Felipe Soares <felipe.staypuff@gmail.com>
(https://github.com/felipesoaresti/)
Version: 1.1 - 20260721
"""

import re

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    Metric,
    Result,
    Service,
    State,
)

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
    decimal_places=0, which reproduces the original (unscaled integer)
    display.
    """
    data = section.get(item)
    if data is None:
        yield Result(state=State.UNKNOWN, summary=f"Not found value for {item}")
        return

    cid = data.get("cid")
    raw_value = data.get("values")
    decimal_places = params.get("decimal_places", 0)

    try:
        scaled_value = int(raw_value) / (10 ** decimal_places)
    except (TypeError, ValueError):
        yield Result(
            state=State.UNKNOWN,
            summary=f"Invalid value '{raw_value}' for {item} ({cid})",
        )
        return

    yield Result(
        state=State.OK,
        summary=f"Current : {scaled_value:.{decimal_places}f} ({cid})",
    )
    # Emitted unconditionally (even with decimal_places=0) so every
    # sensor is graphable/available for historical data from day one.
    yield Metric(_metric_name(item), scaled_value)


check_plugin_modbus = CheckPlugin(
    name="modbus",
    sections=["modbus_value"],
    service_name="Modbus: %s",
    discovery_function=discover_modbus,
    check_function=check_modbus,
    check_ruleset_name="modbus_value_params",
    check_default_parameters={"decimal_places": 0},
)
