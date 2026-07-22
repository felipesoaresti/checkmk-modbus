#!/usr/bin/env python3
"""WATO rule: "Check Modbus devices" (Setup > Agents > Other integrations).

This is a *Special Agent* rule. It configures the datasource program
(`agent_modbus`, see ../libexec/agent_modbus) that is executed to poll one
or more Modbus TCP slaves on this host: for each slave, which TCP port,
which slave/unit id, and which registers (id, word count, counter/gauge
type and a display name) to read from it.

Important, non-obvious behavior (learned the hard way in 1.0.3): Checkmk
evaluates this ruleset with "first matching rule wins" semantics per host,
same as most other host-level parameter rulesets - it is NOT cumulative
across several rules the way some "list" rulesets are. If a host had, say,
three separate "Check Modbus devices" rules (one per physical sensor/slave,
all with the same "Host name is X" condition), only the first one in rule
order would actually be used - agent_modbus would only ever be invoked with
that one rule's slave/registers, and the other two slaves' data would never
show up as services, no matter how parse_modbus() keys its data (this was
mistaken for a parsing bug in 1.0.3 before being traced back to rule
evaluation).

Because of that, this ruleset models "one or more Modbus slaves on the same
host" as a *list inside a single rule* ("slaves" below) rather than relying
on several separate rules - one rule per host is enough to cover any number
of slaves/sensors sharing that host, and there is no ambiguity about which
rule "wins".

Also note (learned in 1.0.7): Checkmk only ever keeps ONE data source per
special agent name per host, so it is NOT possible to make Checkmk itself
invoke agent_modbus once per slave either, even from this single rule's
list. See ../server_side_calls/modbus.py and ../libexec/agent_modbus for
how all configured slaves are instead queried by one single agent_modbus
invocation that loops over them internally, and modbus_value.py for how
the per-slave data is told apart afterwards (each register's "name" must
stay unique across every slave block in the rule).

Changed in version 1.2 (2026-07-22):
  - CLEANUP: renamed the module-level rule spec variable from
    `rule_spec_service_counter` (a leftover, unrelated name) to
    `rule_spec_modbus`. Purely cosmetic - Checkmk discovers rule specs by
    the `rule_spec_` prefix alone, so this has no functional effect; the
    `name="modbus"` argument below (the actual ruleset identifier) was
    already correct.

Original author (through v1.0.2): wellingtonsilva67@gmail.com
Adapted and maintained since v1.0.3 by Felipe Soares <felipe.staypuff@gmail.com>
(https://github.com/felipesoaresti/)
Version: 1.2 - 20260722
"""

from cmk.rulesets.v1 import Title, Help
from cmk.rulesets.v1.form_specs import (
    Dictionary,
    DictElement,
    List,
    SingleChoice,
    SingleChoiceElement,
    String,
    Integer,
    DefaultValue,
)
from cmk.rulesets.v1.form_specs.validators import LengthInRange, NumberInRange
from cmk.rulesets.v1.rule_specs import SpecialAgent, Topic


def _register_dictionary():
    """One Modbus register to poll: id, word count, type and display name.

    Unchanged from 1.0.2/1.0.3 - only where it's nested moved (now one
    level deeper, inside each "slave" block instead of at the rule root).
    """
    return Dictionary(
        elements={
            "cid": DictElement(
                parameter_form=Integer(
                    title=Title("Register ID"),
                ),
                required=True,
            ),
            "words": DictElement(
                parameter_form=SingleChoice(
                    title=Title("Number of words"),
                    elements=[
                        SingleChoiceElement(name="One", title=Title("1 word")),
                        SingleChoiceElement(name="Two", title=Title("2 words")),
                    ],
                    prefill=DefaultValue("One"),
                ),
                required=True,
            ),
            # NOTE: "counter"/"gauge" is consumed by the agent_modbus binary
            # itself (it affects how the C++ code samples/derives the
            # value) - it is *not* related to decimal scaling. Decimal
            # places for display/graphing are configured separately,
            # per-item, via the "Modbus register value scaling" rule in
            # modbus_value_params.py.
            "ctype": DictElement(
                parameter_form=SingleChoice(
                    title=Title("Value Type"),
                    elements=[
                        SingleChoiceElement(name="counter", title=Title("Its a counter value")),
                        SingleChoiceElement(name="gauge", title=Title("Its a gauge value")),
                    ],
                    prefill=DefaultValue("counter"),
                ),
                required=True,
            ),
            # Must be unique across *every* slave block in this rule - this
            # name becomes the Checkmk service item, and is also the key
            # parse_modbus() uses to tell apart registers that share the
            # same Register ID but belong to different slaves.
            "name": DictElement(
                parameter_form=String(
                    title=Title("Register Name"),
                    custom_validate=(LengthInRange(min_value=3),),
                ),
                required=True,
            ),
        },
    )


def _slave_dictionary():
    """One Modbus slave/unit id on this host: port, slave id and its registers."""
    return Dictionary(
        elements={
            "port": DictElement(
                parameter_form=Integer(
                    title=Title("Port"),
                    prefill=DefaultValue(502),
                ),
                required=True,
            ),
            "slave": DictElement(
                parameter_form=Integer(
                    title=Title("slave"),
                    help_text=Help(
                        "Valid slave device addresses are in the range of 0 – 247 decimal. "
                        "For Schneider SLAVE ID = 255."
                    ),
                    prefill=DefaultValue(255),
                    custom_validate=[
                        NumberInRange(min_value=1, max_value=255, error_msg=None),
                    ],
                ),
                required=True,
            ),
            # One slave can have several registers queried at once. Each
            # entry becomes one "<cid>:<words>:<ctype>:<name>" token on the
            # agent_modbus command line for this slave (see
            # ../server_side_calls/modbus.py) and, on success, one line of
            # output under <<<modbus_value>>>, which in turn becomes one
            # Checkmk service (see modbus_value.py).
            "valores": DictElement(
                parameter_form=List(
                    title=Title("Values"),
                    help_text=Help("List of registers to query on this slave."),
                    element_template=_register_dictionary(),
                    custom_validate=(LengthInRange(min_value=1),),
                ),
                required=True,
            ),
        },
    )


def _valuespec_special_agent_modbus():
    return Dictionary(
        title=Title("Check Modbus devices"),
        help_text=Help(
            "Configure one or more Modbus slaves/devices to query on this host. "
            "Add one entry under 'Modbus slaves' per physical sensor/unit id that "
            "shares this host (e.g. several sensors behind the same gateway, each "
            "on its own slave address) - a single rule with several slave entries "
            "is required for this to work, since only the first matching rule for "
            "a host is used. Consult the device documentation to find out which "
            "register ids you want and test them via command line before "
            "configuring the services in the web interface."
        ),
        elements={
            "slaves": DictElement(
                parameter_form=List(
                    title=Title("Modbus slaves"),
                    help_text=Help(
                        "One entry per Modbus slave/unit id to query on this host. "
                        "Add one entry per physical sensor/device that shares this "
                        "host - this is what lets a single Checkmk host represent "
                        "several Modbus slaves at once."
                    ),
                    element_template=_slave_dictionary(),
                    custom_validate=(LengthInRange(min_value=1),),
                ),
                required=True,
            ),
        },
    )


rule_spec_modbus = SpecialAgent(
    name="modbus",
    topic=Topic.APPLICATIONS,
    parameter_form=_valuespec_special_agent_modbus,
    title=Title("Check Modbus devices"),
)
