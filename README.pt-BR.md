🇺🇸 [Read this in English](README.md)

# Checkmk MKP `modbus` — Modbus TCP genérico (v1.0.11)

Plugin Checkmk (2.3.0p26+, testado em 2.4) para monitorar registradores Modbus TCP arbitrários
via o agente especial `agent_modbus` (binário de terceiros,
[vtacquet/agent_modbus](https://github.com/vtacquet/agent_modbus) v2.1). Genérico: funciona com
qualquer dispositivo Modbus, não é específico para os sensores da Sintrex usados como exemplo
aqui.

## Créditos

- **Autor original do plugin Checkmk (até a v1.0.2)**: wellingtonsilva67@gmail.com.
- **Adaptado e mantido desde a v1.0.3 por**: **Felipe Soares** ([github.com/felipesoaresti](https://github.com/felipesoaresti/), felipe.staypuff@gmail.com).
- **Fonte de dados (`agent_modbus`, binário de terceiros)**: Vincent Tacquet
  ([vtacquet/agent_modbus](https://github.com/vtacquet/agent_modbus)).

## Licença

[GPL-2.0-only](LICENSE) para o código próprio deste plugin — veja o arquivo `LICENSE` para o
texto completo. O `agent_modbus_bin` é um binário de terceiros com status de licença próprio,
atualmente não confirmado — veja [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Changelog

Histórico completo de versões: [`CHANGELOG.pt-BR.md`](CHANGELOG.pt-BR.md).

**1.0.11** (atual): organização para publicação no Exchange — relicenciado para GPL-2.0-only,
adicionado `THIRD_PARTY_NOTICES.md`, corrigido o `download_url` do manifesto, reduzida a
descrição do manifesto, removido um arquivo de pacote antigo que tinha ficado para trás. Sem
mudança funcional/de configuração.

## Estrutura deste repositório

```
modbus/
├── README.md                  documentação em inglês
├── README.pt-BR.md            este arquivo (português)
├── CHANGELOG.md                histórico completo de versões (inglês)
├── CHANGELOG.pt-BR.md          histórico completo de versões (português)
├── THIRD_PARTY_NOTICES.md      aviso sobre o binário de terceiros agent_modbus_bin
├── LICENSE                    licença GPL-2.0-only
├── build.sh                   script para gerar o .mkp a partir de src/
├── info / info.json           manifesto do pacote (metadados + versão)
├── modbus-1.0.11.mkp           pacote atual, pronto para instalar
└── src/modbus/
    ├── agent_based/modbus_value.py       parse + discovery + check
    ├── rulesets/modbus.py                 regra "Check Modbus devices" (vários slaves por regra)
    ├── rulesets/modbus_value_params.py    regra "Modbus register value scaling"
    ├── server_side_calls/modbus.py        monta 1 único comando com todos os slaves codificados
    ├── libexec/agent_modbus                orquestrador Python: 1 chamada real por slave, sempre sai 0
    └── libexec/agent_modbus_bin            binário real do agente especial (sem mudança de conteúdo)
```

Versões anteriores do pacote (`modbus-1.0.2.mkp` a `modbus-1.0.9.mkp`) não ficam neste
repositório — só a versão atual é versionada aqui. Se quiser, mantenha um histórico local fora do
Git.

Para reconstruir o `.mkp` depois de editar algo em `src/`:

```sh
./build.sh            # gera modbus-<versão do info.json>.mkp
./build.sh 1.0.11      # ou força uma versão específica
```

Se você tiver acesso a um site Checkmk real, o caminho mais seguro para empacotar é usar as
ferramentas do próprio site (`mkp package modbus` / `cmk-mkp-tool`), que validam a manifest
automaticamente. O `build.sh` deste repositório é a alternativa para gerar o `.mkp` sem precisar
de um site Checkmk disponível (replica byte a byte o formato usado pelo pacote original: tar PAX +
gzip, com `info`, `info.json` e `cmk_addons_plugins.tar`).

## Requisitos

**`libmodbus.so.5` precisa estar instalada em todo servidor Checkmk que rodar esse agente
especial** — o site central e todo site remoto/distribuído, não só no dispositivo Modbus
monitorado. É uma dependência de runtime do binário de terceiros `agent_modbus_bin` (veja
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)), e o pacote **não** instala isso
automaticamente. Se estiver faltando, o `agent_modbus_bin` falha ao carregar e o
`libexec/agent_modbus` engole o erro silenciosamente (por design - ele tolera falha de slave
individual) e sempre sai com código 0, então o agente especial parece ter "rodado normal" mas
não retorna dado nenhum — a descoberta então não encontra nenhum serviço, sem erro nenhum
aparente na UI do Checkmk.

Instale via o gerenciador de pacotes da distribuição:

- **Ubuntu 24.04 (noble)**: `sudo apt-get install libmodbus5` (pacote `3.1.10-1ubuntu1`, no
  repositório `universe`).
- **Ubuntu 22.04 (jammy)**: `sudo apt-get install libmodbus5` (pacote `3.1.6-2`, no
  `universe`; rode `sudo add-apt-repository universe` antes se o apt não achar o pacote).
- **Oracle Linux 8/9**: precisa do EPEL — `sudo dnf install -y oracle-epel-release-el9` (ou
  `-el8`), depois `sudo dnf install -y libmodbus`.

Se o servidor não tiver rota funcional até os repositórios (proxy/firewall corporativo
bloqueando acesso de saída — isso já aconteceu na prática), baixe o `.deb`/`.rpm`
correspondente numa máquina com acesso à internet e copie manualmente:

```sh
# numa máquina com acesso à internet:
curl -LO http://archive.ubuntu.com/ubuntu/pool/universe/libm/libmodbus/libmodbus5_3.1.10-1ubuntu1_amd64.deb
# copie para o servidor de destino (scp) e, no servidor de destino:
sudo dpkg -i libmodbus5_3.1.10-1ubuntu1_amd64.deb
```

De qualquer forma, confirme que a dependência realmente foi resolvida antes de considerar o
plugin corrigido:

```sh
sudo -u cmk ldd /omd/sites/<nome_do_site>/local/lib/python3/cmk_addons/plugins/modbus/libexec/agent_modbus_bin
```

`libmodbus.so.5` precisa mostrar um caminho real, não `=> not found`.

## Instalação

1. Se uma versão anterior estiver instalada, remova-a primeiro (Setup > Extension packages, ou
   `mkp remove modbus <versão>`) — evita conflito de arquivos entre versões.
2. **Setup > Extension packages > Upload package** e envie `modbus-1.0.11.mkp`, ou via linha de
   comando no site: `mkp add modbus-1.0.11.mkp && mkp enable modbus 1.0.11`.
3. Ative as mudanças pendentes (ícone de mudanças pendentes no topo).
4. Configure a regra "Check Modbus devices" no formato atual — ver "Como configurar" abaixo.
5. Rode **Services > Rediscover services** nos hosts afetados.

## Como configurar

### 1. Regra "Check Modbus devices"

`Setup > Agents > Other integrations > Check Modbus devices`. **Uma única regra por host** (mesmo
que o host tenha vários sensores/slaves Modbus — o Checkmk só permite 1 execução do agente por
host, então tudo precisa estar dentro dessa regra). Estrutura:

- **Modbus slaves**: lista — um item por slave/unit id que existir nesse host. Para cada slave:
  - **Port**: porta TCP do Modbus (normalmente 502).
  - **slave**: endereço do slave Modbus (1–255).
  - **Values**: lista de registradores a consultar nesse slave. Para cada um:
    - **Register ID**: endereço do registrador no dispositivo.
    - **Number of words**: 1 ou 2 words.
    - **Value Type**: `counter` ou `gauge` — consumido pelo binário `agent_modbus` para a
      semântica interna de amostragem, **não tem relação com casas decimais**.
    - **Register Name**: nome livre, vira o nome do serviço no Checkmk. **Importante**: precisa
      ser único entre todos os slaves dentro da mesma regra, mesmo que os Register IDs se repitam
      entre slaves diferentes (é esse nome que identifica cada sensor internamente).

Exemplo para um host com 3 sensores (Core, Fitoteca, Servidores) — **1 regra**, com **3
entradas** em "Modbus slaves":

| Slave | Port | Registros (Register ID → Register Name)                                                    |
|-------|------|----------------------------------------------------------------------------------------------|
| 1     | 502  | 26 → `ID1_Bateria-Core`, 28 → `ID1_Temperatura-Core`, 29 → `ID1_Umidade-Core`                |
| 2     | 502  | 26 → `ID1_Bateria-Fitoteca`, 28 → `ID1_Temperatura-Fitoteca`, 29 → `ID1_Umidade-Fitoteca`     |
| 3     | 502  | 26 → `ID1_Bateria-Servidores`, 28 → `ID1_Temperatura-Servidores`, 29 → `ID1_Umidade-Servidores` |

### 2. Regra "Modbus register value scaling"

`Setup > Services > Service monitoring rules > Modbus register value scaling` (ou busque por
"Modbus" na busca de regras). Regra de parâmetros de serviço, casada por **host + item** (nome do
serviço). Campos:

- **Decimal places**: quantas casas decimais aplicar ao valor bruto antes de exibir/gravar como
  métrica. O valor bruto é dividido por `10^N`.
- **Unit**: texto livre anexado logo após o valor escalado, ex.: `%` (sem espaço) ou ` °C` (com
  espaço no início) — deixe vazio para mostrar só o número (comportamento anterior).
- **Interpret as signed 16-bit integer**: habilite para registradores que podem ler valores
  negativos (ex.: um sensor de temperatura abaixo de zero). Valores brutos de 32768-65535 são
  convertidos via complemento de dois de 16 bits (`valor - 65536`) antes de escalar. Só se aplica
  a registradores de 1 palavra (16 bits).
- **Levels (upper)** / **Levels (lower)**: limites opcionais de WARN/CRIT aplicados ao valor
  escalado, cada um alternando independentemente entre "No levels" (padrão, sempre OK —
  comportamento anterior) e "Fixed levels". Use "Levels (upper)" para alertar quando o valor
  sobe demais (ex.: temperatura) e "Levels (lower)" para alertar quando desce demais (ex.:
  bateria baixa, ou temperatura muito fria — valores negativos de WARN/CRIT são válidos aqui,
  já que a temperatura é signed). Um registrador pode usar um, os dois, ou nenhum.

> Nota: essa regra aparece tanto em **Service monitoring rules** quanto em **Enforced services**
> — isso é comportamento normal do Checkmk para esse tipo de regra (parâmetro por item), não é
> duplicidade nem bug. Use **Service monitoring rules**, que é o menu para ajustar parâmetros de
> serviços já descobertos.

Exemplos para o caso da Sintrex (bateria/temperatura/umidade, conforme o mapa Modbus do sensor:
bateria é % sem sinal, temperatura é °C com sinal e 2 casas decimais implícitas, umidade é % sem
sinal com 2 casas decimais implícitas). Como o casamento é por regex de item, **uma única regra
por "tipo" de registrador cobre todos os slaves/locais**:

| Condição do item (regex)                        | Decimal places | Unit  | Signed | Levels (upper)     | Levels (lower)      | Resultado                |
|---------------------------------------------------|-----------------|-------|--------|----------------------|------------------------|---------------------------|
| item começa com `Bateria-` (qualquer local)       | 0               | `%`   | não    | nenhum               | WARN 20 / CRIT 10      | `100` → `100%`; `5` → `5%` CRIT |
| item começa com `Temperatura-` (qualquer local)   | 2               | ` °C` | sim    | WARN 30 / CRIT 35    | WARN -5 / CRIT -10     | `2419` → `24.19 °C`; `65036` → `-5.00 °C` WARN |
| item começa com `Umidade-` (qualquer local)       | 2               | `%`   | não    | nenhum               | nenhum                 | `3538` → `35.38%`         |

Os exemplos de bateria/temperatura acima são ilustrativos — não há nada no código amarrando
esses limites a um registrador específico; digite os valores de WARN/CRIT que fizerem sentido
para os seus sensores ao configurar a regra.

## Saída do serviço

Antes (1.0.2, sem decimais e sem os slaves adicionais):
```
Modbus: ID1_Temperatura-Core   OK   Current : 2419 (28)
```

Depois (1.0.7, com a regra de escala e todos os slaves na mesma regra):
```
Modbus: Temperatura-Core       OK   Current : 23.69 (28)
Modbus: Temperatura-Fitoteca   OK   Current : 22.42 (28)
```

Depois (1.0.8, com unit e signed também configurados):
```
Modbus: Bateria-Core           OK   Current : 100% (26)
Modbus: Temperatura-Core       OK   Current : 23.69 °C (28)
Modbus: Umidade-Core           OK   Current : 58.42% (29)
```

Depois (1.0.10, com levels também configurados — bateria baixa e leitura fria):
```
Modbus: Bateria-Core           CRIT   Current : 5% (warn/crit below 20%/10%) (26)
Modbus: Temperatura-Core       WARN   Current : -6.50 °C (warn/crit below -5.00 °C/-10.00 °C) (28)
Modbus: Umidade-Core           OK     Current : 58.42% (29)
```
e cada serviço passa a ter uma métrica graficável (histórico/Perf-O-Meter), sombreada com os
limites configurados quando levels estão definidos.

## Limitações conhecidas / pontos de atenção

- `agent_modbus_bin` é um binário compilado de terceiros; este plugin não recompila nem modifica
  seu comportamento — casas decimais e múltiplos slaves por host são resolvidos inteiramente do
  lado Python do plugin (rulesets, server_side_calls e o orquestrador `libexec/agent_modbus`).
- O Checkmk permite só **1 execução de agente especial por host**, sempre — por isso a regra
  "Check Modbus devices" precisa ser **1 regra por host** com todos os slaves dentro dela; não há
  como contornar isso criando várias regras separadas.
- Se um slave nunca responder (dispositivo físico com problema), seus serviços **não aparecem na
  descoberta automática** até ele responder pelo menos uma vez; depois de descobertos, se pararem
  de responder, ficam `UNKNOWN` (não somem, mas também não travam o resto do host).
- `Register Name` precisa continuar único dentro da mesma regra (entre todos os slaves) — isso
  não é validado automaticamente entre entradas diferentes (só o tamanho mínimo de 3 caracteres é
  validado no campo em si).
- A assinatura exata da API `CheckParameters`/`HostAndItemCondition` usada em
  `rulesets/modbus_value_params.py` foi escrita conforme a documentação da `cmk.rulesets.v1` para
  regras de parâmetros por item; já validada funcionando ao vivo num Checkmk 2.4.0p18.
