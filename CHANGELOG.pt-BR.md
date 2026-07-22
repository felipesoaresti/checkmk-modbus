# Changelog

Todas as mudanças relevantes do pacote Checkmk `modbus`.

## 1.0.11 — organização para publicação no Exchange

Sem mudança funcional/de configuração. Relicenciado o código próprio do plugin (rulesets,
server_side_calls, check agent_based, orquestrador `libexec/agent_modbus`) de MIT para
**GPL-2.0-only**, alinhado com a exigência de licenciamento do Checkmk para extensões que usam suas
APIs internas. Adicionado `THIRD_PARTY_NOTICES.md` documentando o binário de terceiros
`agent_modbus_bin` (autor, projeto upstream, dependência de runtime `libmodbus`, e o status de
licença atualmente não confirmado). Corrigido o `download_url` do `info.json`/`info` para apontar
para este repositório em vez de uma URL de perfil genérica, e reduzida a `description` do
manifesto para um resumo curto (o changelog completo agora vive aqui em vez de duplicado no
manifesto). Removido o arquivo `modbus-1.0.8.mkp`, que tinha ficado rastreado no git por engano
depois de ser substituído.

Follow-up só de documentação (ainda 1.0.11, sem mudança no pacote/manifesto): adicionada uma
seção "Requisitos" nos dois READMEs deixando explícito que a `libmodbus.so.5` precisa estar
instalada em todo servidor Checkmk que rodar esse agente especial (site central e sites
remotos/distribuídos), com comandos de instalação para Ubuntu 24.04/22.04 e Oracle Linux,
alternativa offline via `.deb`/`.rpm`, e um comando de verificação. Isso foi motivado por um
caso real de implantação em que o plugin funcionava no site de teste mas não retornava dado
nenhum, silenciosamente, num site distribuído de produção, por causa exatamente dessa
dependência faltando — a falha não é óbvia pela UI do Checkmk, já que o wrapper do agente
sempre sai com código 0 de qualquer forma. O `THIRD_PARTY_NOTICES.md` agora referencia essa
seção em vez de só mencionar a dependência de passagem.

## 1.0.10 — refactor interno: usar o helper oficial `check_levels()`

Sem mudança de configuração. Auditei o plugin contra a documentação oficial de desenvolvedor do
Checkmk (`devel_check_plugins`, `devel_special_agents`, referências da API `cmk.agent_based`/
`cmk.rulesets`/`cmk.server_side_calls`): as convenções de nomenclatura (prefixos
`agent_section_`, `check_plugin_`, `rule_spec_`, `special_agent_`) e o layout de diretórios já
estavam corretos, mas a comparação de WARN/CRIT adicionada na 1.0.9 era feita manualmente em vez
de usar `cmk.agent_based.v2.check_levels()` — o jeito documentado e padrão de avaliar um valor
contra um parâmetro `levels_upper`/`levels_lower`. Troquei para usar o helper (comportamento
confirmado equivalente testando direto contra a API real em um site Checkmk 2.4.0p18). Também
renomeei uma variável interna em `rulesets/modbus.py`, de `rule_spec_service_counter` (nome que
sobrou de outro lugar) para `rule_spec_modbus` (cosmético — o prefixo `rule_spec_` já estava certo,
então isso não tem efeito funcional).

**Pequena diferença visível**: quando um limite é violado, o texto `(warn/crit at ...)` agora
aparece *antes* do sufixo `(<cid>)` em vez de depois, ex.: `Current : 32.00 °C (warn/crit at
30.00 °C/35.00 °C) (28)` em vez de `Current : 32.00 °C (28) (warn/crit at 30.00 °C/35.00 °C)`.
O caso OK sem levels (a grande maioria dos serviços) fica igual.

## 1.0.9 — limites de alerta (WARN/CRIT) por registrador

A regra "Modbus register value scaling" ganhou mais dois campos: **Levels (upper)** e
**Levels (lower)**, cada um um limite WARN/CRIT independente e opcional sobre o valor escalado
(o toggle padrão do Checkmk "No levels / Fixed levels"). Antes, o check sempre devolvia `OK`
independente do valor lido — não havia como alertar sobre bateria baixa, sensor superaquecendo,
etc. Ambos usam "No levels" por padrão, então regras/instalações existentes continuam se
comportando exatamente como antes.

Quando um limite é cruzado, o serviço vai para `WARN`/`CRIT` e o resumo ganha um sufixo - `(warn/
crit at X/Y)` para violação do limite superior, `(warn/crit below X/Y)` para violação do limite
inferior (esse texto vem do próprio `check_levels()` do Checkmk, não é algo que o plugin
escolhe). Ex.: `Current : 5% (warn/crit below 20%/10%) (26)` para bateria baixa. Os limites são
avaliados como comparações de `float` puras, então valores negativos de WARN/CRIT funcionam
corretamente para o registrador signed de temperatura (ex.: alertar quando ela cai abaixo de um
valor negativo configurado). O gráfico da métrica só ganha a faixa de limiar sombreada a partir
de **Levels (upper)** — o `check_levels()` nunca anexa o **Levels (lower)** ao gráfico, mesmo
quando é ele que está configurado; o *estado* do serviço reage corretamente aos dois lados de
qualquer forma, só a faixa sombreada no gráfico é exclusiva do limite superior.

## 1.0.8 — mostrar unidade (%, °C) e corrigir registradores signed de 16 bits

A regra "Modbus register value scaling" ganhou dois campos, além do já existente "Decimal
places":

- **Unit**: um sufixo de texto livre anexado após o valor escalado (ex.: `%` ou ` °C`), exibido
  no resumo do serviço. Necessário para mostrar bateria/umidade como porcentagem e temperatura em
  Celsius, conforme configurado para os sensores Sintrex.
- **Interpret as signed 16-bit integer**: o registrador de temperatura dos sensores Sintrex é um
  valor de 16 bits *com sinal* (pode ler abaixo de zero), mas o check anteriormente sempre tratava
  o valor bruto como sem sinal, então uma leitura negativa (ex.: bruto `65036` para `-5.00 °C`)
  aparecia como `650.36`. Habilitar essa opção aplica complemento de dois de 16 bits antes de
  escalar. Só se aplica a registradores de 1 palavra (16 bits).

Ambos os campos mantêm o comportamento anterior por padrão (sem unidade, sem sinal), então
instalações e regras existentes não são afetadas até serem explicitamente configuradas. O campo
`author` do `info.json` também foi corrigido para seguir o formato
`(https://github.com/felipesoaresti/)` usado no restante do plugin.

## 1.0.7 — corrigido de vez: só 1 execução de agente por host

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

## 1.0.6 — falha de 1 slave não deveria mais derrubar os outros (superada pela 1.0.7)

Tentativa (incompleta, ver 1.0.7 acima): renomear o binário compilado para
`libexec/agent_modbus_bin` e transformar `libexec/agent_modbus` num wrapper `/bin/sh` que sempre
sai com código 0. Isolava corretamente o *código de saída*, mas não resolvia o problema real
porque o Checkmk nunca chegava a rodar mais de 1 comando por host — ver 1.0.7.

## 1.0.5 — autoria do pacote

Só metadados do manifesto (`info`/`info.json`): campos `author` e `download_url` atualizados
para refletir que este plugin é adaptado e mantido por Felipe Soares, mantendo o crédito técnico
ao `agent_modbus`/Vincent Tacquet e ao autor original do plugin na descrição. Sem mudança de
código/lógica.

## 1.0.4 — vários slaves numa regra só (formato de configuração)

Depois de testar a 1.0.3 ao vivo, confirmou-se que **casas decimais e o parsing por nome
funcionam perfeitamente**, mas hosts com **várias regras** "Check Modbus devices" (uma por slave)
continuavam mostrando só os serviços da primeira regra.

Causa raiz identificada nessa época (parcial — a causa completa só foi entendida na 1.0.7): o
Checkmk avalia essa regra com semântica de "primeira regra que casa vence" por host. Como fix
imediato, a regra "Check Modbus devices" passou a modelar **"um ou mais slaves Modbus" dentro de
uma única regra** (campo "Modbus slaves", uma lista — ver "Como configurar" no README), formato
que **continua sendo o correto** mesmo depois do fix definitivo da 1.0.7 (só mudou *como* o
Checkmk executa o agente por trás dos panos, não como o usuário configura a regra).

## 1.0.3 — casas decimais + parsing por nome

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
