# Changelog

All notable changes to the `modbus` Checkmk package.

## 1.0.11 — housekeeping for Exchange publication

No functional/config changes. Relicensed the plugin's own code (rulesets, server_side_calls,
agent_based check, `libexec/agent_modbus` orchestrator) from MIT to **GPL-2.0-only**, in line with
Checkmk's licensing requirements for extensions that use its internal APIs. Added
`THIRD_PARTY_NOTICES.md` documenting the bundled third-party `agent_modbus_bin` binary (author,
upstream project, runtime dependency on `libmodbus`, and its currently unconfirmed license status).
Corrected `info.json`/`info`'s `download_url` to point at this repository instead of a generic
profile URL, and trimmed the manifest `description` down to a short summary (the full changelog
now lives here instead of being duplicated into the manifest). Removed the stray
`modbus-1.0.8.mkp` package file that had stayed tracked in git by mistake after being superseded.

Documentation-only follow-up (still 1.0.11, no package/manifest change): added a "Requirements"
section to both READMEs spelling out that `libmodbus.so.5` must be installed on every Checkmk
server running this special agent (central and remote/distributed sites alike), with install
commands for Ubuntu 24.04/22.04 and Oracle Linux, an offline `.deb`/`.rpm` fallback, and a
verification command. This was prompted by a real deployment where the plugin worked on a test
site but silently returned no data on a distributed production site because of this exact missing
dependency - the failure mode is not obvious from the Checkmk UI, since the agent wrapper always
exits 0 regardless. `THIRD_PARTY_NOTICES.md` now cross-references this section instead of just
mentioning the dependency in passing.

## 1.0.10 — internal refactor: use the documented `check_levels()` helper

No config changes. Audited the plugin against Checkmk's official developer documentation
(`devel_check_plugins`, `devel_special_agents`, the `cmk.agent_based`/`cmk.rulesets`/
`cmk.server_side_calls` API references): naming conventions (`agent_section_`, `check_plugin_`,
`rule_spec_`, `special_agent_` prefixes) and directory layout were already correct, but the
WARN/CRIT comparison added in 1.0.9 was hand-rolled instead of using
`cmk.agent_based.v2.check_levels()` - the documented, standard way to evaluate a value against a
`levels_upper`/`levels_lower` parameter. Switched to it (behavior confirmed equivalent by testing
directly against the real API on a Checkmk 2.4.0p18 site). Also renamed an internal rule-spec
variable in `rulesets/modbus.py` from the leftover `rule_spec_service_counter` to
`rule_spec_modbus` (cosmetic only - the `rule_spec_` prefix was already correct, so this has no
functional effect).

**Small visible difference**: when a level is breached, the `(warn/crit at ...)` text now comes
*before* the `(<cid>)` suffix instead of after it, e.g. `Current : 32.00 °C (warn/crit at 30.00
°C/35.00 °C) (28)` instead of `Current : 32.00 °C (28) (warn/crit at 30.00 °C/35.00 °C)`. The
OK-with-no-levels case (the vast majority of services) is unchanged.

## 1.0.9 — WARN/CRIT thresholds (levels) per register

The "Modbus register value scaling" rule gained two more fields: **Levels (upper)** and
**Levels (lower)**, each an independent, optional WARN/CRIT threshold on the scaled value (the
standard Checkmk "No levels / Fixed levels" toggle). Previously the check always returned `OK`
regardless of the value read - there was no way to alert on a low battery, an overheating sensor,
etc. Both default to "No levels" so existing rules/installs keep behaving exactly as before.

When a level is crossed, the service goes `WARN`/`CRIT` and the summary gains a suffix - `(warn/
crit at X/Y)` for an upper breach, `(warn/crit below X/Y)` for a lower one (Checkmk's own
`check_levels()` wording, not something this plugin picks). E.g. `Current : 5% (warn/crit below
20%/10%) (26)` for a low battery. Thresholds are evaluated as plain float comparisons, so
negative WARN/CRIT values work correctly for the signed temperature register (e.g. alerting when
it drops below a configured negative value). The metric's graph only ever gets a shaded
threshold band from **Levels (upper)** - `check_levels()` never attaches `Levels (lower)` to the
graph, even when it's the one configured; the service *state* still reacts correctly to either
side either way, only the graph shading is upper-only.

## 1.0.8 — show unit (%, °C) and fix signed 16-bit registers

The "Modbus register value scaling" rule gained two fields, alongside the existing "Decimal
places":

- **Unit**: a free-form suffix appended after the scaled value (e.g. `%` or ` °C`), shown in the
  service summary. Needed to display battery/humidity as a percentage and temperature in Celsius,
  as configured for the Sintrex sensors.
- **Interpret as signed 16-bit integer**: the temperature register on the Sintrex sensors is a
  *signed* 16-bit value (it can read below zero), but the check previously always treated raw
  values as unsigned, so a negative reading (e.g. raw `65036` for `-5.00 °C`) would display as
  `650.36` instead. Enabling this option applies 16-bit two's complement before scaling. Only
  applies to one-word (16-bit) registers.

Both fields default to their previous behavior (no unit, unsigned) so existing installs and rules
are unaffected until explicitly configured. `info.json`'s `author` field was also corrected to
match the `(https://github.com/felipesoaresti/)` format used everywhere else in the plugin.

## 1.0.7 — actually fixed this time: only 1 agent execution per host

1.0.6 tried to isolate a single slave's failure by having Checkmk run one `agent_modbus` command
per slave (within the same rule). Live testing showed this never really worked: even with 2 of 3
slaves responding fine, Checkmk kept reporting "Found no services" - not even the healthy slaves
showed up.

Definitive diagnosis (read directly from the installed Checkmk 2.4.0p18 source, not a guess): in
`cmk/base/sources/_builder.py`, `_add()` stores each data source in a dict
`self._elems[source.source_info().ident] = source`; and in `cmk/base/sources/_sources.py`,
`SpecialAgentSource.source_info()` always returns `ident = f"special_{agent_name}"` - i.e.
always `"special_modbus"`, no matter how many commands the rule yields. Since it's a dict, every
command we yield overwrites the previous one - **only the last one survives and actually runs**.
Confirmed live by instrumenting the wrapper with invocation logging: only 1 call ever happened,
with the last slave's arguments.

Conclusion: **Checkmk only ever allows 1 data source per special agent name per host, period** -
there is no way to make one rule trigger several real executions of the same special agent on
the same host. The 1.0.4-1.0.6 architecture could never have worked for multiple slaves.

**Real fix**: `server_side_calls/modbus.py` now yields **exactly one command**, encoding every
slave configured in the rule into a single argument list (each slave block introduced by the
`--slave` marker). `libexec/agent_modbus` is no longer a simple wrapper - it's now a small Python
orchestrator: it splits the blocks, calls the real binary (`agent_modbus_bin`) **once per slave**
internally, concatenates whichever ones responded, silently skips whichever ones failed, and
always exits 0. Tested and validated live: with 2 of 3 slaves responding, Checkmk now correctly
discovers and checks the 2 working ones, decimal scaling included.

**Expected side effect**: a slave that has never responded still **won't show up in autodiscovery**
(there is no data from it to discover) - this only changes once the physical sensor responds at
least once during a re-discovery.

## 1.0.6 — one slave failing shouldn't take down the others (superseded by 1.0.7)

Attempt (incomplete, see 1.0.7 above): rename the compiled binary to `libexec/agent_modbus_bin`
and turn `libexec/agent_modbus` into a `/bin/sh` wrapper that always exits 0. This correctly
isolated the *exit code*, but didn't fix the real problem, since Checkmk never actually ran more
than one command per host in the first place - see 1.0.7.

## 1.0.5 — package authorship

Manifest metadata only (`info`/`info.json`): `author` and `download_url` fields updated to
reflect that this plugin is adapted and maintained by Felipe Soares, while keeping the technical
credit to `agent_modbus`/Vincent Tacquet and to the original plugin author in the description. No
code/logic change.

## 1.0.4 — several slaves in one rule (configuration format)

After testing 1.0.3 live, it was confirmed that **decimal places and name-based parsing work
perfectly**, but hosts with **several** "Check Modbus devices" rules (one per slave) still only
showed the first rule's services.

Root cause identified at the time (partial - the full cause was only understood in 1.0.7):
Checkmk evaluates this rule with "first matching rule wins" semantics per host. As an immediate
fix, the "Check Modbus devices" rule started modeling "one or more Modbus slaves" **inside a
single rule** (the "Modbus slaves" list field - see the README's "Configuration" section), a
format that **remains correct** even after the definitive 1.0.7 fix (only *how* Checkmk runs the
agent behind the scenes changed, not how the user configures the rule).

## 1.0.3 — decimal places + name-based parsing

Version 1.0.2 had two problems, fixed in this version:

1. **Parsing indexed by Register ID (`cid`) instead of name.** When two or more "Check Modbus
   devices" rules targeted the same host, reusing the same register IDs per slave, readings from
   different slaves overwrote each other in the parser. Fixed in `parse_modbus` (now indexes by
   `Register Name`, unique per slave).
2. **No decimal places in the displayed/graphed values.** The raw register value (an integer with
   no decimal separator - e.g. `2419` for a real reading of `24.19`) went straight into the
   service text with no conversion at all, and the check never emitted a `Metric`. Fixed with the
   new **"Modbus register value scaling"** WATO rule, matched by service name (item), where you
   configure how many decimal places to apply (the raw value is divided by `10^N`). A service with
   no matching rule keeps the previous behavior (integer, no decimals). The check now also emits
   a `Metric`, so every sensor becomes graphable even without configuring the new rule.

In no version was it necessary to modify `agent_modbus` itself (compiled binary, outside our
control) - the fixes live entirely on the Python side of the plugin.
