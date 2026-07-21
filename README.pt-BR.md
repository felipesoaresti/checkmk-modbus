🇺🇸 [Read this in English](README.md)

# Checkmk MKP `modbus` — Modbus TCP genérico (v1.0.7)

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

[MIT](LICENSE) — veja o arquivo `LICENSE` para o texto completo.

## Changelog

### 1.0.7 — corrigido de vez: só 1 execução de agente por host

A 1.0.6 tentou isolar a falha de 1 slave fazendo o Checkmk rodar 1 comando `agent_modbus` por
slave (dentro da mesma regra). Ao testar ao vivo, descobrimos que isso **nunca funcionou de
verdade**: mesmo com 2 dos 3 slaves respondendo bem, o Checkmk continuava reportando
"Found no services" — nem os slaves saudáveis apareciam.

Diagnóstico definitivo (lendo o código-fonte real do Checkmk 2.4.0p18 instalado, não suposição):
em `cmk/base/sources/_builder.py`, o método `_add()` guarda cada fonte de dados num dicionário
`self._elems[source.source_info().ident] = source`; e em `cmk/base/sources/_sources.py`,
`SpecialAgentSource.source_info()` sempre devolve `ident = f"special_{agent_name}"` — ou seja,
sempre `"special_modbus"`, não importa quantos comandos a regra gere. Como é um dicionário, cada
comando nosso sobrescreve o anterior — **só o último sobrevive e é executado**. Confirmamos isso
instrumentando o wrapper com log de invocações ao vivo: só 1 chamada aconteceu, com os argumentos
do último slave da lista.

Conclusão: **o Checkmk só permite 1 fonte de dados por nome de agente especial por host, sempre**
— não existe um jeito de fazer uma regra gerar múltiplas execuções reais do mesmo agente especial
num mesmo host. A arquitetura das versões 1.0.4 a 1.0.6 nunca poderia ter funcionado para múltiplos
slaves.

**Fix real**: `server_side_calls/modbus.py` agora gera **1 único comando**, com todos os slaves
configurados na regra codificados numa única linha de argumentos (cada bloco de slave separado
pelo marcador `--slave`). `libexec/agent_modbus` deixou de ser um wrapper simples e virou um
orquestrador em Python: ele separa os blocos, chama o binário real (`agent_modbus_bin`) **uma vez
por slave** internamente, concatena a saída de quem respondeu, ignora silenciosamente quem falhou,
e sempre sai com código 0. Testado e validado ao vivo: com 2 de 3 slaves respondendo, o Checkmk
agora descobre e verifica corretamente os 2 que funcionam, com casas decimais aplicadas.

**Efeito colateral esperado**: um slave que nunca respondeu ainda **não aparece na descoberta
automática** (não há dado nenhum vindo dele para descobrir) — isso só muda quando o sensor físico
voltar a responder pelo menos uma vez durante uma redescoberta.

### 1.0.6 — falha de 1 slave não deveria mais derrubar os outros (superada pela 1.0.7)

Tentativa (incompleta, ver 1.0.7 acima): renomear o binário compilado para
`libexec/agent_modbus_bin` e transformar `libexec/agent_modbus` num wrapper `/bin/sh` que sempre
sai com código 0. Isolava corretamente o *código de saída*, mas não resolvia o problema real
porque o Checkmk nunca chegava a rodar mais de 1 comando por host — ver 1.0.7.

### 1.0.5 — autoria do pacote

Só metadados do manifesto (`info`/`info.json`): campos `author` e `download_url` atualizados
para refletir que este plugin é adaptado e mantido por Felipe Soares, mantendo o crédito técnico
ao `agent_modbus`/Vincent Tacquet e ao autor original do plugin na descrição. Sem mudança de
código/lógica.

### 1.0.4 — vários slaves numa regra só (formato de configuração)

Depois de testar a 1.0.3 ao vivo, confirmou-se que **casas decimais e o parsing por nome
funcionam perfeitamente**, mas hosts com **várias regras** "Check Modbus devices" (uma por slave)
continuavam mostrando só os serviços da primeira regra.

Causa raiz identificada nessa época (parcial — a causa completa só foi entendida na 1.0.7): o
Checkmk avalia essa regra com semântica de "primeira regra que casa vence" por host. Como fix
imediato, a regra "Check Modbus devices" passou a modelar **"um ou mais slaves Modbus" dentro de
uma única regra** (campo "Modbus slaves", uma lista — ver "Como configurar" abaixo), formato que
**continua sendo o correto** mesmo depois do fix definitivo da 1.0.7 (só mudou *como* o Checkmk
executa o agente por trás dos panos, não como o usuário configura a regra).

### 1.0.3 — casas decimais + parsing por nome

A versão 1.0.2 tinha dois problemas, corrigidos nesta versão:

1. **Parsing indexava por Register ID (`cid`) em vez de nome.** Quando duas ou mais regras "Check
   Modbus devices" apontavam para o mesmo host reaproveitando os mesmos IDs de registrador por
   slave, as leituras se sobrescreviam no parser. Corrigido em `parse_modbus` (agora indexa por
   `Register Name`, único por slave).
2. **Sem casas decimais na exibição/gráfico dos valores.** O valor bruto do registrador (inteiro,
   sem separador decimal — ex. `2419` para uma leitura real de `24.19`) ia direto para o texto do
   serviço, sem nenhuma conversão, e o check nunca emitia `Metric`. Corrigido com a nova regra
   WATO **"Modbus register value scaling"**, associada por nome de serviço (item), onde se
   configura quantas casas decimais aplicar (o valor bruto é dividido por `10^N`). Um serviço sem
   regra correspondente mantém o comportamento antigo (inteiro, sem decimais). O check agora
   também emite `Metric`, então todo sensor passa a ser graficável mesmo sem configurar a nova
   regra.

Em nenhuma versão foi necessário alterar `agent_modbus` (binário compilado, fora do nosso
controle) — as correções ficam inteiramente do lado Python do plugin.

## Estrutura deste repositório

```
modbus/
├── README.md                  documentação em inglês
├── README.pt-BR.md            este arquivo (português)
├── LICENSE                    licença MIT
├── build.sh                   script para gerar o .mkp a partir de src/
├── info / info.json           manifesto do pacote (metadados + versão)
├── modbus-1.0.7.mkp            pacote atual, pronto para instalar
└── src/modbus/
    ├── agent_based/modbus_value.py       parse + discovery + check
    ├── rulesets/modbus.py                 regra "Check Modbus devices" (vários slaves por regra)
    ├── rulesets/modbus_value_params.py    regra "Modbus register value scaling"
    ├── server_side_calls/modbus.py        monta 1 único comando com todos os slaves codificados
    ├── libexec/agent_modbus                orquestrador Python: 1 chamada real por slave, sempre sai 0
    └── libexec/agent_modbus_bin            binário real do agente especial (sem mudança de conteúdo)
```

Versões anteriores do pacote (`modbus-1.0.2.mkp` a `modbus-1.0.6.mkp`) não ficam neste
repositório — só a versão atual é versionada aqui. Se quiser, mantenha um histórico local fora do
Git.

Para reconstruir o `.mkp` depois de editar algo em `src/`:

```sh
./build.sh            # gera modbus-<versão do info.json>.mkp
./build.sh 1.0.8       # ou força uma versão específica
```

Se você tiver acesso a um site Checkmk real, o caminho mais seguro para empacotar é usar as
ferramentas do próprio site (`mkp package modbus` / `cmk-mkp-tool`), que validam a manifest
automaticamente. O `build.sh` deste repositório é a alternativa para gerar o `.mkp` sem precisar
de um site Checkmk disponível (replica byte a byte o formato usado pelo pacote original: tar PAX +
gzip, com `info`, `info.json` e `cmk_addons_plugins.tar`).

## Instalação

1. Se uma versão anterior estiver instalada, remova-a primeiro (Setup > Extension packages, ou
   `mkp remove modbus <versão>`) — evita conflito de arquivos entre versões.
2. **Setup > Extension packages > Upload package** e envie `modbus-1.0.7.mkp`, ou via linha de
   comando no site: `mkp add modbus-1.0.7.mkp && mkp enable modbus 1.0.7`.
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
serviço). Campo único:

- **Decimal places**: quantas casas decimais aplicar ao valor bruto antes de exibir/gravar como
  métrica. O valor bruto é dividido por `10^N`.

> Nota: essa regra aparece tanto em **Service monitoring rules** quanto em **Enforced services**
> — isso é comportamento normal do Checkmk para esse tipo de regra (parâmetro por item), não é
> duplicidade nem bug. Use **Service monitoring rules**, que é o menu para ajustar parâmetros de
> serviços já descobertos.

Exemplos para o caso da Sintrex (registradores de temperatura/umidade com 2 casas decimais
implícitas, bateria sem escala). Como o casamento é por regex de item, **uma única regra cobre
todos os slaves/locais**:

| Condição do item (regex)                    | Decimal places | Resultado                    |
|-----------------------------------------------|-----------------|-------------------------------|
| item começa com `Temperatura-` (qualquer local) | 2               | `2419` → `24.19`              |
| item começa com `Umidade-` (qualquer local)     | 2               | `3538` → `35.38`               |
| (sem regra / item de bateria)                   | 0 (default)     | `100` → `100` (sem mudança)   |

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
e cada serviço passa a ter uma métrica graficável (histórico/Perf-O-Meter).

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
