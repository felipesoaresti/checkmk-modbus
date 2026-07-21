#!/usr/bin/env python3
"""WATO rule: "Modbus register value scaling" (check parameters, matched by item).

Companion rule to "Check Modbus devices" (modbus.py). While that rule
configures *what* gets polled from a Modbus slave (registers, word
counts, names), this rule configures *how the resulting value is
displayed and graphed* on a per-service basis: raw register values are
plain integers with no decimal point (e.g. a raw reading of 2419 for a
temperature register that is really 24.19 degrees), and the number of
implied decimal places is a property of the sensor/register, not of
the transport - so it has to be configurable independently, and it
must not require touching the agent_modbus binary or its command-line
arguments (see modbus_value.py's module docstring for why).

This is a *CheckParameters* rule, matched by host + service item
(HostAndItemCondition), which is what lets a single rule apply to many
services at once via an item regex - e.g. one rule matching every
service whose item contains "Temperatura" across any number of hosts
and Modbus slaves, without having to enumerate each service name. This
is what keeps the plugin generic for future Modbus devices: whatever a
device's registers are named, the user writes one scaling rule per
"kind" of register (temperature, humidity, ...), not one per physical
sensor.

A register with no matching rule falls back to
check_default_parameters={"decimal_places": 0} in modbus_value.py,
i.e. the original unscaled integer display - so existing installs are
unaffected until the user opts in.

Author: Felipe Soares <felipe.staypuff@gmail.com> (https://github.com/felipesoaresti/)
Version: 1.0 - 20260721
"""

from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import Dictionary, DictElement, Integer, DefaultValue
from cmk.rulesets.v1.form_specs.validators import NumberInRange
from cmk.rulesets.v1.rule_specs import CheckParameters, HostAndItemCondition, Topic


def _parameter_form_modbus_value_params():
    return Dictionary(
        title=Title("Modbus register value scaling"),
        help_text=Help(
            "Number of decimal places to apply to the raw integer value read "
            "from the Modbus register before it is displayed and graphed. "
            "The raw value is divided by 10^N. Leave the default (0) to keep "
            "the value unscaled (previous behavior)."
        ),
        elements={
            "decimal_places": DictElement(
                parameter_form=Integer(
                    title=Title("Decimal places"),
                    help_text=Help(
                        "Example: a raw value of 2419 with 2 decimal places "
                        "is shown/graphed as 24.19."
                    ),
                    prefill=DefaultValue(0),
                    custom_validate=(
                        NumberInRange(min_value=0, max_value=6, error_msg=None),
                    ),
                ),
                required=True,
            ),
        },
    )


# NOTE: `name` below must match `check_ruleset_name="modbus_value_params"`
# in modbus_value.py exactly - these are free-form strings with no static
# check tying them together.
rule_spec_modbus_value_params = CheckParameters(
    name="modbus_value_params",
    title=Title("Modbus register value scaling"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_modbus_value_params,
    condition=HostAndItemCondition(item_title=Title("Register name (service item)")),
)
