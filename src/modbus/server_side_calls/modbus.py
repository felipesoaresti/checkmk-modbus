#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Builds the agent_modbus command line from a "Check Modbus devices" rule.

Confirmed by reading Checkmk 2.4.0p18's own source
(cmk/base/sources/_builder.py `_add()` and
cmk/base/sources/_sources.py `SpecialAgentSource.source_info()`): Checkmk
only ever keeps ONE source per special agent name per host - every
SpecialAgentCommand this module could yield gets the same
`ident = f"special_{agent_name}"` (i.e. always "special_modbus"), and
`_add()` stores sources in a plain `dict[ident] = source`, so yielding
several commands from one rule does NOT run agent_modbus several times;
each later command silently overwrites the earlier one in that dict, and
only the LAST yielded command ever actually executes. This was the real
reason multiple Modbus slaves configured in one rule (see
../rulesets/modbus.py) never all showed up: only the last slave's command
line was ever run.

Because of that, this function yields exactly ONE SpecialAgentCommand,
whose arguments encode *every* configured slave, each block introduced by
the literal marker "--slave". The actual per-slave looping (calling the
real agent_modbus binary once per slave and tolerating individual
failures) happens in ../libexec/agent_modbus, the only place that can
still run the compiled binary more than once for this host.

Original author (through v1.0.2): wellingtonsilva67@gmail.com
Adapted and maintained since v1.0.3 by Felipe Soares <felipe.staypuff@gmail.com>
(https://github.com/felipesoaresti/)
Version: 1.2 - 20260721
"""

from typing import Iterator

from pydantic import BaseModel

from cmk.server_side_calls.v1 import (
    HostConfig,
    SpecialAgentCommand,
    SpecialAgentConfig,
)


class ModbusParams(BaseModel):
    slaves: list


def generate_modbus_command(
    params: ModbusParams,
    host_config: HostConfig,
) -> Iterator[SpecialAgentCommand]:
    address = host_config.primary_ip_config.address
    args: list[str] = [address]
    for slave_cfg in params.slaves:
        args.append("--slave")
        args.append(str(slave_cfg["port"]))
        args.append(str(slave_cfg["slave"]))
        for valor in slave_cfg["valores"]:
            words = str(valor["words"]).replace("One", "1").replace("Two", "2")
            name = str(valor["name"]).replace(" ", "_")
            args.append(f"{valor['cid']}:{words}:{valor['ctype']}:{name}")
    yield SpecialAgentCommand(command_arguments=args)


special_agent_modbus = SpecialAgentConfig(
    name="modbus",
    parameter_parser=ModbusParams.model_validate,
    commands_function=generate_modbus_command,
)
