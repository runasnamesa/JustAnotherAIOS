---
description: Entrevista de ~20 min, uma pergunta por vez, para escrever o primeiro rascunho da memória.
host: mac
---
Você vai montar a memória deste AIOS a partir de uma entrevista comigo. Regras:

- **Uma pergunta por vez.** Espere minha resposta antes da próxima. Máximo ~20 perguntas.
- Cubra, nesta ordem: quem sou e o que faço; áreas da minha vida/trabalho (proponha 4–7);
  o que faço semana a semana; com quem trabalho; onde meus arquivos vivem hoje;
  o que se repete e poderia virar rotina; o que nunca pode ser enviado sem mim.
- Ao final, mostre o plano (áreas, notas por área, rotinas sugeridas) e **peça confirmação**.
- Só depois de confirmado, escreva:
  1. `CLAUDE.md` raiz — no máximo ~40 linhas, **sem fatos**: só "Quem sou" (2–3 linhas),
     uma linha por área apontando para `[[areas/<area>/CLAUDE]]`, regras e roteamento de modelo.
  2. `areas/<area>/CLAUDE.md` — placa da área: uma linha por nota ("o que tem / quando abrir").
  3. As notas, cada uma com frontmatter `summary:` de uma linha. Cada fato em um só lugar.
  4. Sugestões de rotina em `pulse/routines.toml` com `enabled = false` (eu ligo depois).
- Remova as notas marcadas "_(exemplo)_" que não se aplicarem.
- No fim rode `python3 -m aios brain` e `python3 -m aios lint` e corrija até o lint passar.
