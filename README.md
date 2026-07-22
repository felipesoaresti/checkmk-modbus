🇧🇷 [Leia em português](README.pt-BR.md)

# Checkmk MKP `modbus` — generic Modbus TCP monitoring (v1.0.11)

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

[GPL-2.0-only](LICENSE) for this plugin's own code — see the `LICENSE` file for the full text.
`agent_modbus_bin` is a bundled third-party binary with its own, currently unconfirmed license
status — see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Changelog

Full version history: [`CHANGELOG.md`](CHANGELOG.md).

**1.0.11** (current): housekeeping for Exchange publication — relicensed to GPL-2.0-only, added
`THIRD_PARTY_NOTICES.md`, corrected the manifest's `download_url`, trimmed the manifest
description, removed a stray old package file. No functional/config changes.

## Repository layout

```
modbus/
├── README.md                  this file (English)
├── README.pt-BR.md            Portuguese documentation
├── CHANGELOG.md                full version history (English)
├── CHANGELOG.pt-BR.md          full version history (Portuguese)
├── THIRD_PARTY_NOTICES.md      notice for the bundled agent_modbus_bin binary
├── LICENSE                    GPL-2.0-only license
├── build.sh                   script to build the .mkp from src/
├── info / info.json           package manifest (metadata + version)
├── modbus-1.0.11.mkp           current package, ready to install
└── src/modbus/
    ├── agent_based/modbus_value.py       parse + discovery + check
    ├── rulesets/modbus.py                 "Check Modbus devices" rule (several slaves per rule)
    ├── rulesets/modbus_value_params.py    "Modbus register value scaling" rule
    ├── server_side_calls/modbus.py        builds 1 single command encoding every slave
    ├── libexec/agent_modbus                Python orchestrator: 1 real call per slave, always exits 0
    └── libexec/agent_modbus_bin            the real special agent binary (content unchanged)
```

Previous package builds (`modbus-1.0.2.mkp` through `modbus-1.0.9.mkp`) are not kept in this
repository - only the current version is version-controlled here. Keep a local history outside
Git if you want one.

To rebuild the `.mkp` after editing anything under `src/`:

```sh
./build.sh            # builds modbus-<version from info.json>.mkp
./build.sh 1.0.11      # or force a specific version
```

If you have access to a real Checkmk site, the safest way to package is to use the site's own
tooling (`mkp package modbus` / `cmk-mkp-tool`), which validates the manifest automatically. This
repository's `build.sh` is the alternative for building the `.mkp` without a Checkmk site
available (it replicates byte-for-byte the format used by the original package: PAX tar + gzip,
with `info`, `info.json` and `cmk_addons_plugins.tar`).

## Installation

1. If a previous version is installed, remove it first (Setup > Extension packages, or
   `mkp remove modbus <version>`) - avoids file conflicts between versions.
2. **Setup > Extension packages > Upload package** and upload `modbus-1.0.11.mkp`, or via the
   site's command line: `mkp add modbus-1.0.11.mkp && mkp enable modbus 1.0.11`.
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
- **Levels (upper)** / **Levels (lower)**: optional WARN/CRIT thresholds applied to the scaled
  value, each independently toggled between "No levels" (default, always OK - previous behavior)
  and "Fixed levels". Use "Levels (upper)" to alert when the value rises too high (e.g.
  temperature) and "Levels (lower)" to alert when it drops too low (e.g. low battery, or a
  temperature that's too cold - negative WARN/CRIT values are valid here, since temperature is
  signed). A register can use either, both, or neither.

> Note: this rule shows up both under **Service monitoring rules** and **Enforced services** -
> that's normal Checkmk behavior for this kind of rule (per-item parameter), not a duplicate or a
> bug. Use **Service monitoring rules**, which is the menu for adjusting parameters of already
> discovered services.

Examples for the Sintrex case (battery/temperature/humidity registers, per the sensor's Modbus
map: battery is unsigned %, temperature is signed °C with 2 implied decimal places, humidity is
unsigned % with 2 implied decimal places). Since matching is done via item regex, **a single rule
per "kind" of register covers every slave/location**:

| Item condition (regex)                          | Decimal places | Unit  | Signed | Levels (upper) | Levels (lower)  | Result                  |
|--------------------------------------------------|-----------------|-------|--------|-----------------|------------------|--------------------------|
| item starts with `Bateria-` (any location)       | 0               | `%`   | no     | none            | WARN 20 / CRIT 10 | `100` → `100%`; `5` → `5%` CRIT |
| item starts with `Temperatura-` (any location)   | 2               | ` °C` | yes    | WARN 30 / CRIT 35 | WARN -5 / CRIT -10 | `2419` → `24.19 °C`; `65036` → `-5.00 °C` WARN |
| item starts with `Umidade-` (any location)       | 2               | `%`   | no     | none            | none             | `3538` → `35.38%`        |

The battery/temperature examples above are illustrative - there's nothing in the code tying
these thresholds to any specific register; enter whatever WARN/CRIT values make sense for your
sensors when configuring the rule.

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

After (1.0.10, with levels also configured - a low battery and a cold reading):
```
Modbus: Bateria-Core           CRIT   Current : 5% (warn/crit below 20%/10%) (26)
Modbus: Temperatura-Core       WARN   Current : -6.50 °C (warn/crit below -5.00 °C/-10.00 °C) (28)
Modbus: Umidade-Core           OK     Current : 58.42% (29)
```
and each service now has a graphable metric (history/Perf-O-Meter), shaded with the configured
thresholds when levels are set.

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
