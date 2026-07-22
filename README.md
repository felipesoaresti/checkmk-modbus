🇧🇷 [Leia em português](README.pt-BR.md)

# Checkmk MKP `modbus` — generic Modbus TCP monitoring (v1.0.8)

Checkmk plugin (2.3.0p26+, tested on 2.4) for monitoring arbitrary Modbus TCP registers via the
`agent_modbus` special agent (third-party binary,
[vtacquet/agent_modbus](https://github.com/vtacquet/agent_modbus) v2.1). Generic: works with any
Modbus device, it is not specific to the Sintrex sensors used as an example here.

## Credits

- **Original author of the Checkmk plugin (through v1.0.2)**: wellingtonsilva67@gmail.com.
- **Adapted and maintained since v1.0.3 by**: **Felipe Soares**
  ([github.com/felipesoaresti](https://github.com/felipesoaresti/), felipe.staypuff@gmail.com).
- **Data source (`agent_modbus`, third-party binary)**: Vincent Tacquet
  ([vtacquet/agent_modbus](https://github.com/vtacquet/agent_modbus)).

## License

[MIT](LICENSE) — see the `LICENSE` file for the full text.

## Changelog

### 1.0.8 — show unit (%, °C) and fix signed 16-bit registers

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

### 1.0.7 — actually fixed this time: only 1 agent execution per host

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

### 1.0.6 — one slave failing shouldn't take down the others (superseded by 1.0.7)

Attempt (incomplete, see 1.0.7 above): rename the compiled binary to `libexec/agent_modbus_bin`
and turn `libexec/agent_modbus` into a `/bin/sh` wrapper that always exits 0. This correctly
isolated the *exit code*, but didn't fix the real problem, since Checkmk never actually ran more
than one command per host in the first place - see 1.0.7.

### 1.0.5 — package authorship

Manifest metadata only (`info`/`info.json`): `author` and `download_url` fields updated to
reflect that this plugin is adapted and maintained by Felipe Soares, while keeping the technical
credit to `agent_modbus`/Vincent Tacquet and to the original plugin author in the description. No
code/logic change.

### 1.0.4 — several slaves in one rule (configuration format)

After testing 1.0.3 live, it was confirmed that **decimal places and name-based parsing work
perfectly**, but hosts with **several** "Check Modbus devices" rules (one per slave) still only
showed the first rule's services.

Root cause identified at the time (partial - the full cause was only understood in 1.0.7):
Checkmk evaluates this rule with "first matching rule wins" semantics per host. As an immediate
fix, the "Check Modbus devices" rule started modeling "one or more Modbus slaves" **inside a
single rule** (the "Modbus slaves" list field - see "Configuration" below), a format that
**remains correct** even after the definitive 1.0.7 fix (only *how* Checkmk runs the agent behind
the scenes changed, not how the user configures the rule).

### 1.0.3 — decimal places + name-based parsing

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

## Repository layout

```
modbus/
├── README.md                  this file (English)
├── README.pt-BR.md            Portuguese documentation
├── LICENSE                    MIT license
├── build.sh                   script to build the .mkp from src/
├── info / info.json           package manifest (metadata + version)
├── modbus-1.0.8.mkp            current package, ready to install
└── src/modbus/
    ├── agent_based/modbus_value.py       parse + discovery + check
    ├── rulesets/modbus.py                 "Check Modbus devices" rule (several slaves per rule)
    ├── rulesets/modbus_value_params.py    "Modbus register value scaling" rule
    ├── server_side_calls/modbus.py        builds 1 single command encoding every slave
    ├── libexec/agent_modbus                Python orchestrator: 1 real call per slave, always exits 0
    └── libexec/agent_modbus_bin            the real special agent binary (content unchanged)
```

Previous package builds (`modbus-1.0.2.mkp` through `modbus-1.0.7.mkp`) are not kept in this
repository - only the current version is version-controlled here. Keep a local history outside
Git if you want one.

To rebuild the `.mkp` after editing anything under `src/`:

```sh
./build.sh            # builds modbus-<version from info.json>.mkp
./build.sh 1.0.9       # or force a specific version
```

If you have access to a real Checkmk site, the safest way to package is to use the site's own
tooling (`mkp package modbus` / `cmk-mkp-tool`), which validates the manifest automatically. This
repository's `build.sh` is the alternative for building the `.mkp` without a Checkmk site
available (it replicates byte-for-byte the format used by the original package: PAX tar + gzip,
with `info`, `info.json` and `cmk_addons_plugins.tar`).

## Installation

1. If a previous version is installed, remove it first (Setup > Extension packages, or
   `mkp remove modbus <version>`) - avoids file conflicts between versions.
2. **Setup > Extension packages > Upload package** and upload `modbus-1.0.8.mkp`, or via the
   site's command line: `mkp add modbus-1.0.8.mkp && mkp enable modbus 1.0.8`.
3. Activate pending changes (the pending-changes icon at the top).
4. Configure the "Check Modbus devices" rule in the current format - see "Configuration" below.
5. Run **Services > Rediscover services** on the affected hosts.

## Configuration

### 1. "Check Modbus devices" rule

`Setup > Agents > Other integrations > Check Modbus devices`. **A single rule per host** (even if
the host has several Modbus sensors/slaves - Checkmk only allows 1 agent execution per host, so
everything needs to live inside this one rule). Structure:

- **Modbus slaves**: a list - one entry per slave/unit id on this host. For each slave:
  - **Port**: the Modbus TCP port (usually 502).
  - **slave**: the Modbus slave address (1-255).
  - **Values**: the list of registers to query on this slave. For each one:
    - **Register ID**: the register's address on the device.
    - **Number of words**: 1 or 2 words.
    - **Value Type**: `counter` or `gauge` - consumed by the `agent_modbus` binary for its
      internal sampling semantics, **not related to decimal places**.
    - **Register Name**: free-form text, becomes the Checkmk service name. **Important**: must be
      unique across every slave within the same rule, even if Register IDs repeat across
      different slaves (this name is what identifies each sensor internally).

Example for a host with 3 sensors (Core, Fitoteca, Servidores) - **1 rule**, with **3 entries**
under "Modbus slaves":

| Slave | Port | Registers (Register ID → Register Name)                                                    |
|-------|------|----------------------------------------------------------------------------------------------|
| 1     | 502  | 26 → `ID1_Bateria-Core`, 28 → `ID1_Temperatura-Core`, 29 → `ID1_Umidade-Core`                |
| 2     | 502  | 26 → `ID1_Bateria-Fitoteca`, 28 → `ID1_Temperatura-Fitoteca`, 29 → `ID1_Umidade-Fitoteca`     |
| 3     | 502  | 26 → `ID1_Bateria-Servidores`, 28 → `ID1_Temperatura-Servidores`, 29 → `ID1_Umidade-Servidores` |

### 2. "Modbus register value scaling" rule

`Setup > Services > Service monitoring rules > Modbus register value scaling` (or search for
"Modbus" in the rule search). A service parameter rule, matched by **host + item** (service
name). Fields:

- **Decimal places**: how many decimal places to apply to the raw value before displaying/graphing
  it. The raw value is divided by `10^N`.
- **Unit**: free-form text appended right after the scaled value, e.g. `%` (no leading space) or
  ` °C` (with a leading space) - leave empty to show just the number (previous behavior).
- **Interpret as signed 16-bit integer**: enable for registers that can read negative (e.g. a
  temperature sensor below zero). Raw values of 32768-65535 are converted via 16-bit two's
  complement (`value - 65536`) before scaling. Only applies to one-word (16-bit) registers.

> Note: this rule shows up both under **Service monitoring rules** and **Enforced services** -
> that's normal Checkmk behavior for this kind of rule (per-item parameter), not a duplicate or a
> bug. Use **Service monitoring rules**, which is the menu for adjusting parameters of already
> discovered services.

Examples for the Sintrex case (battery/temperature/humidity registers, per the sensor's Modbus
map: battery is unsigned %, temperature is signed °C with 2 implied decimal places, humidity is
unsigned % with 2 implied decimal places). Since matching is done via item regex, **a single rule
per "kind" of register covers every slave/location**:

| Item condition (regex)                          | Decimal places | Unit  | Signed | Result                  |
|--------------------------------------------------|-----------------|-------|--------|--------------------------|
| item starts with `Bateria-` (any location)       | 0               | `%`   | no     | `100` → `100%`           |
| item starts with `Temperatura-` (any location)   | 2               | ` °C` | yes    | `2419` → `24.19 °C`; `65036` → `-5.00 °C` |
| item starts with `Umidade-` (any location)       | 2               | `%`   | no     | `3538` → `35.38%`        |

## Service output

Before (1.0.2, no decimals, no additional slaves):
```
Modbus: ID1_Temperatura-Core   OK   Current : 2419 (28)
```

After (1.0.7, with the scaling rule and every slave in the same rule):
```
Modbus: Temperatura-Core       OK   Current : 23.69 (28)
Modbus: Temperatura-Fitoteca   OK   Current : 22.42 (28)
```

After (1.0.8, with unit and signed also configured):
```
Modbus: Bateria-Core           OK   Current : 100% (26)
Modbus: Temperatura-Core       OK   Current : 23.69 °C (28)
Modbus: Umidade-Core           OK   Current : 58.42% (29)
```
and each service now has a graphable metric (history/Perf-O-Meter).

## Known limitations / things to watch for

- `agent_modbus_bin` is a compiled third-party binary; this plugin never recompiles or changes its
  behavior - decimal places and multiple slaves per host are resolved entirely on the Python side
  of the plugin (rulesets, server_side_calls, and the `libexec/agent_modbus` orchestrator).
- Checkmk only ever allows **1 special agent execution per host** - so the "Check Modbus devices"
  rule needs to be **one rule per host** with every slave inside it; there is no way around this
  by creating several separate rules.
- If a slave never responds (a physical device issue), its services **won't show up in
  autodiscovery** until it responds at least once; once discovered, if it stops responding again,
  they go `UNKNOWN` (they don't disappear, and they don't block the rest of the host either).
- `Register Name` must stay unique within the same rule (across every slave) - this isn't
  automatically validated across different entries (only the 3-character minimum length is
  validated on the field itself).
- The exact `CheckParameters`/`HostAndItemCondition` API signature used in
  `rulesets/modbus_value_params.py` was written per the `cmk.rulesets.v1` documentation for
  per-item parameter rules; already validated working live on a Checkmk 2.4.0p18 site.
