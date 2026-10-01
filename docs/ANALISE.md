# Análise crítica: o que vale copiar do vídeo, o que é risco, o que mudei

## O que é forte (e foi mantido)

- **Arquivos simples como fonte da verdade.** Troca de modelo/ferramenta sem migração.
- **"Mostra, nunca guarda".** O painel é descartável; elimina toda uma classe de bugs de sincronia.
- **VPS que só rascunha.** Automação sem supervisão + capacidade de enviar = risco desproporcional.
- **Tailscale em vez de porta pública.** Superfície de ataque perto de zero.
- **Uma lista que espera humano, e só o humano fecha.** Evita o agente "resolver" coisas no papel.

## Onde o vídeo exagera ou deixa lacunas

1. **"40% menos tokens" é anedota, não evidência.** Uma pergunta, duas execuções, e os números
   falados (28k → 17k) não batem com os da tela (23.9k → 14.5k). Provavelmente o mapa ajuda;
   *quanto* depende da sua base. Por isso existe `aios.measure`: mesma pergunta, cópia com e sem
   mapa, N execuções, média ± desvio e checagem de acerto (`--expect`). Rode com 3–5 perguntas
   reais antes de acreditar.
2. **Trava por prompt não é trava.** "Claude se recusou a enviar" só vale se a ferramenta não
   existir para ele. Aqui a VPS usa `defaultMode: dontAsk` + allowlist mínima; a denylist é
   reforço. Regras de Bash não pegam `sh -c` nem caminho absoluto — se quiser garantia de SO,
   ative o sandbox.
3. **Injeção de prompt é o risco real.** Rotinas que leem conteúdo externo (e-mail, web) podem
   receber instruções maliciosas. Mitigações aplicadas: sem rede, sem MCP, escrita só em
   `areas/` e `drafts/`, histórico git para reverter. **Recomendação:** rotina que lê conteúdo
   externo deve escrever só em `drafts/`, nunca na memória.
4. **Sync git a cada 5 min nos dois sentidos gera conflito** quando as duas máquinas escrevem o
   mesmo arquivo. Mitigação: estado por host (`runs/state-<host>.json`), cada rotina escreve
   arquivos próprios, e o sync aborta e avisa em vez de forçar. Regra: **um escritor por arquivo**.
   Efeito colateral: até ~288 commits/dia por máquina — aceitável, mas considere um repo só de dados.
5. **Seus dados de negócio passam a morar no GitHub.** Repo privado não é cofre. Para áreas
   sensíveis (finanças, saúde, clientes sob NDA), avalie `git-crypt` ou mantê-las fora do sync.
6. **Termos de uso.** Rodar o próprio Claude Code na própria VPS com sua conta é o caminho que o
   vídeo usa; harness de terceiros com a assinatura, não. Verifique os termos vigentes do seu
   plano, e lembre que as duas máquinas dividem os mesmos limites de uso — daí o teto diário e a
   pausa por falhas.
7. **O painel é ~20% do valor** (o próprio autor diz). Começar por ele é o erro mais comum.

## O que fiz diferente

| Vídeo | Aqui | Por quê |
|---|---|---|
| `routines.yaml` | `routines.toml` | `tomllib` é stdlib: zero dependências |
| lint de placas | lint + "MAP.md velho" + "raiz gorda" + saltos | o mapa não pode mentir |
| "cap" não detalhado | pausa após N falhas + teto diário por host | custo previsível |
| botões disparam na máquina certa | pedido em `runs/queue/` viaja pelo git | sem porta aberta entre máquinas |
| 6 vistas (incl. 3D) | 2 vistas (Anéis, Links) | 3D é estética; adicione se fizer falta |

## Não validado neste ambiente (teste você)

- launchd no Mac, systemd/Tailscale na VPS, bot do Telegram com a API real, transcrição de voz
  no servidor, e o comportamento das regras de permissão numa sessão real (`/permissions`).
- Os testes automatizados (`tests/`) cobrem cron, memória/lint, fila/pulse com Claude falso,
  servidor (traversal, cabeçalho anti-CSRF, alvos desconhecidos), allowlist do bot e a medição.
