# CLAUDE.md — roteador mestre

Este arquivo não guarda fatos: só diz onde cada coisa mora. Para qualquer pergunta:
1. Olhe `map/MAP.md` (índice gerado, uma linha por nota) **ou** a placa da área abaixo.
2. Abra só a nota apontada. Meta: qualquer fato em até 2 saltos a partir daqui.

## Quem sou
<!-- 2–3 linhas. Rode /interview para preencher. -->
Dono deste workspace. Prefere respostas diretas, com riscos e contrapontos.

## Áreas (uma linha por área → placa da área)
- Projetos — o que estou construindo e o estado de cada um → [[areas/projetos/CLAUDE]]
- Trabalho — clientes, pipeline, propostas → [[areas/trabalho/CLAUDE]]
- Conteúdo — posts, vídeos, guia de estilo → [[areas/conteudo/CLAUDE]]
- Pessoal — saúde, finanças, casa → [[areas/pessoal/CLAUDE]]
- Sistema — agenda, pendências, regras do próprio AIOS → [[areas/sistema/CLAUDE]]

## Regras
- Todo fato tem exatamente uma casa. Nunca escreva o mesmo fato em dois arquivos: aponte.
- Criou/moveu nota? Atualize a placa da área e rode `python -m aios brain`.
- `areas/sistema/precisa-de-voce.md` é a única lista que espera um humano. Você pode
  adicionar itens `- [ ]`; **nunca** marque como feito — só o humano marca.
- Nada é enviado para terceiros sem pedido explícito: e-mail, post e mensagem viram rascunho.
- O painel (`screen/`) só mostra. Nenhum fato mora nele.

## Roteamento de modelo
- Busca, resumo, triagem: modelo rápido/barato. Escrita final e decisões: modelo principal.
