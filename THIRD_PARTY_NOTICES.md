# Third-party notices

This package (`modbus`) bundles one third-party binary artifact that is not covered by this
repository's own `LICENSE` (GPL-2.0-only). This file documents it.

## `agent_modbus_bin` (`src/modbus/libexec/agent_modbus_bin`)

- **What it is**: the compiled Modbus TCP special-agent binary that this plugin's
  `libexec/agent_modbus` orchestrator invokes once per configured slave. It is the actual program
  that talks Modbus TCP to the target device and prints the `<<<modbus_value>>>` agent section this
  plugin's check parses.
- **Upstream project**: [`vtacquet/agent_modbus`](https://github.com/vtacquet/agent_modbus).
- **Author**: Vincent Tacquet.
- **Version identification**: the binary is not stripped and embeds the string
  `agent_modbus - Vincent Tacquet - 2024 - vincent.tacquet@gmail.com`. The maintainer of this
  repository has not pinned an exact upstream commit/tag for the bundled build.
- **Runtime dependency**: dynamically linked against `libmodbus.so.5` (confirmed via `ldd`), plus
  the standard `libstdc++`, `libc`, `libm`, `libgcc_s`. `libmodbus` must be installed on **every**
  Checkmk server that runs this special agent (central and remote/distributed sites alike) - the
  package does not bundle or install it. See the README's ["Requirements"](README.md#requirements)
  section (or [`README.pt-BR.md#requisitos`](README.pt-BR.md#requisitos)) for install commands per
  distro and how to tell it's missing (the failure is silent - the agent wrapper exits 0 either
  way). Built for Linux x86_64.
- **License status**: **not confirmed.** No license file or SPDX identifier is embedded in the
  binary itself, and no license text for `agent_modbus` or its `libmodbus` dependency is
  reproduced in this repository. The upstream project's own licensing terms have not been
  independently verified or cleared with the author by the current maintainer of this plugin.
  This is a known open item, called out here rather than glossed over, so that anyone
  redistributing this package (including Checkmk Exchange moderators) is aware of it.

If you are the author of `agent_modbus` (Vincent Tacquet) or otherwise able to clarify the license
terms for this binary, please open an issue on this repository.
