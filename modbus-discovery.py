###Utilitario criado para conectar a um sensor Modbus e descobrir quais Unit IDs estão respondendo, além de ler alguns registradores de exemplo.
# Autor: Felipe dos Santos Soares - felipe.staypuff@gmail.com
# version: 1.0

#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any, Callable

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

HOST = "10.2.1.176"
PORT = 502

# O padrão Modbus permite IDs mais altos, mas o JSON atual utiliza 1 a 10.
# Para uma primeira execução mais rápida, use range(1, 21).
UNIT_IDS = range(1, 248)

TIMEOUT = 0.35
DELAY_BETWEEN_UNITS = 0.02


def modbus_call(
    method: Callable[..., Any],
    address: int,
    *,
    count: int,
    unit_id: int,
) -> Any:
    """
    Compatibilidade com versões do PyModbus que usam:
      - device_id= nas versões recentes;
      - slave= em versões anteriores.
    """
    try:
        return method(
            address,
            count=count,
            device_id=unit_id,
        )
    except TypeError:
        return method(
            address,
            count=count,
            slave=unit_id,
        )


def valid_response(response: Any) -> bool:
    return response is not None and not response.isError()


def signed_int16(value: int) -> int:
    return value - 65536 if value & 0x8000 else value


def format_mac(registers: list[int]) -> str:
    """
    Junta quatro registradores de 16 bits em um número de 64 bits.

    Como o JSON não informa claramente a ordem das palavras do MAC,
    mostramos os registradores brutos e usamos os últimos 48 bits
    como uma interpretação provável.
    """
    value = 0

    for register in registers:
        value = (value << 16) | register

    mac_hex = f"{value:016X}"[-12:]

    return ":".join(mac_hex[index : index + 2] for index in range(0, 12, 2))


def discover_unit(client: ModbusTcpClient, unit_id: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "unit_id": unit_id,
        "respondendo": False,
    }

    # Bateria: Holding Register 26
    try:
        response = modbus_call(
            client.read_holding_registers,
            26,
            count=1,
            unit_id=unit_id,
        )

        if valid_response(response):
            result["respondendo"] = True
            result["bateria_raw"] = response.registers[0]
            result["bateria"] = response.registers[0]

    except (ModbusException, OSError):
        pass

    # Temperatura e umidade: Holding Registers 28 e 29
    try:
        response = modbus_call(
            client.read_holding_registers,
            28,
            count=2,
            unit_id=unit_id,
        )

        if valid_response(response):
            result["respondendo"] = True

            temperature_raw = response.registers[0]
            humidity_raw = response.registers[1]

            result["temperatura_raw"] = temperature_raw
            result["umidade_raw"] = humidity_raw

            result["temperatura"] = signed_int16(temperature_raw) * 0.01
            result["umidade"] = humidity_raw * 0.01

    except (ModbusException, OSError):
        pass

    # Entradas digitais: Input Status 60 e 61
    try:
        response = modbus_call(
            client.read_discrete_inputs,
            60,
            count=2,
            unit_id=unit_id,
        )

        if valid_response(response):
            result["respondendo"] = True

            input_1 = bool(response.bits[0])
            input_2 = bool(response.bits[1])

            # Conforme textRenderer do JSON:
            # 0 = ON
            # 1 = OFF
            result["entrada_1_raw"] = int(input_1)
            result["entrada_2_raw"] = int(input_2)
            result["entrada_1"] = "OFF" if input_1 else "ON"
            result["entrada_2"] = "OFF" if input_2 else "ON"

    except (ModbusException, OSError):
        pass

    # MAC: quatro Holding Registers a partir de 5980
    try:
        response = modbus_call(
            client.read_holding_registers,
            5980,
            count=4,
            unit_id=unit_id,
        )

        if valid_response(response):
            result["respondendo"] = True
            result["mac_registers"] = response.registers
            result["mac_provavel"] = format_mac(response.registers)

    except (ModbusException, OSError):
        pass

    return result


def main() -> int:
    client = ModbusTcpClient(
        HOST,
        port=PORT,
        timeout=TIMEOUT,
        retries=0,
    )

    if not client.connect():
        print(f"ERRO: não foi possível conectar a {HOST}:{PORT}")
        return 1

    print(f"Conectado a {HOST}:{PORT}")
    print("Procurando sensores Modbus...\n")

    discovered = 0

    try:
        for unit_id in UNIT_IDS:
            data = discover_unit(client, unit_id)

            if not data["respondendo"]:
                continue

            discovered += 1

            print(f"Unit ID {unit_id}: RESPONDENDO")

            if "temperatura" in data:
                print(
                    f"  Temperatura : "
                    f"{data['temperatura']:.2f} °C "
                    f"(raw={data['temperatura_raw']})"
                )

            if "umidade" in data:
                print(
                    f"  Umidade     : "
                    f"{data['umidade']:.2f}% "
                    f"(raw={data['umidade_raw']})"
                )

            if "bateria" in data:
                print(f"  Bateria     : {data['bateria']}% (raw={data['bateria_raw']})")

            if "entrada_1" in data:
                print(
                    f"  Entrada 1   : {data['entrada_1']} (raw={data['entrada_1_raw']})"
                )

            if "entrada_2" in data:
                print(
                    f"  Entrada 2   : {data['entrada_2']} (raw={data['entrada_2_raw']})"
                )

            if "mac_registers" in data:
                print(f"  MAC provável: {data['mac_provavel']}")
                print(f"  MAC raw     : {data['mac_registers']}")

            print()

            time.sleep(DELAY_BETWEEN_UNITS)

    finally:
        client.close()

    print(f"Total de Unit IDs respondendo: {discovered}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
