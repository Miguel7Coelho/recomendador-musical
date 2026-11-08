# Design system: recomendador musical

Fonte da verdade do visual. Os valores vivem em `src/index.css`; mudou aqui, muda lá.

## Direção

**Família: equipamento de estúdio, denso em dados.** A tela lembra um módulo de rack: superfícies
escuras, divisórias finas, rótulos pequenos e leituras numéricas grandes. O público é quem produz
música, então tom, Camelot e BPM são protagonistas, não detalhes.

Da referência de UX (samplette.io) vem só o fluxo: uma recomendação por vez e ações rápidas. A
identidade visual é própria.

Princípios:

1. **O dado é a decoração.** Nada de ilustração ou ornamento: o que dá caráter é a leitura de tom,
   BPM e confiança.
2. **Um único sinal.** O âmbar marca a ação principal e o que está tocando. Se tudo brilha, nada
   brilha.
3. **Relaxamento é informação, não erro.** Com 399 faixas o filtro de tom é relaxado em quase toda
   consulta; o aviso usa o azul informativo e tom neutro.
4. **Honestidade do modelo.** Toda inferência mostra a confiança, e o que o modelo não sabe fica
   oculto (ex.: tipo de voz quando `vocal_gender` é `null`).

## Evitar

Gradientes roxos ou azuis, vidro fosco, brilho em volta de botões, cartões com cantos muito
arredondados e sombra difusa, grade de três cartões com ícone, emoji como ícone, texto em gradiente,
títulos genéricos ("Descubra sua música") e animação sem função.

## Cores

Tema escuro único no MVP (uso em estúdio, com pouca luz).

| Token | Valor | Uso |
|---|---|---|
| `bg` | `#121110` | fundo da página |
| `surface` | `#1b1a18` | painéis |
| `raised` | `#25231f` | hover, chips, campos |
| `line` | `#38352f` | divisórias decorativas |
| `control` | `#7d766a` | borda de controles interativos |
| `text` | `#ece7dc` | texto principal e leituras |
| `muted` | `#a39c8e` | rótulos e texto secundário |
| `accent` | `#f2a93b` | ação principal, faixa tocando, foco |
| `on-accent` | `#1a1408` | texto sobre `accent` |
| `info` | `#8fb8d8` | relaxamento e avisos neutros |
| `ok` | `#7fc48a` | confiança alta, sucesso |
| `danger` | `#ec7a6a` | erros |

Regra: texto e ícones em AA (4,5:1) sobre `bg`, `surface` e `raised`; bordas de controles em 3:1.
Cor nunca é o único sinal: estados também têm texto ou ícone.

## Tipografia

- **Archivo** (variável): interface, títulos e metadados.
- **IBM Plex Mono**: tudo que é medido (tom, Camelot, BPM, score, confiança, tempo).

| Token | Tamanho / altura | Uso |
|---|---|---|
| `label` | 11/16, mono, maiúsculas, espaçado | rótulos de leitura e seção |
| `small` | 13/20 | crédito, explicação |
| `body` | 15/24 | texto corrente, controles |
| `title` | 22/28, 600 | nome da faixa |
| `readout` | 40/44, mono, 500 | tom e BPM em destaque |

Números sempre com `tabular-nums`. Decimais em vírgula (pt-BR).

## Espaçamento e forma

- Grade de 4 px: `1, 2, 3, 4, 6, 8, 12` (escala padrão do Tailwind).
- Painéis com divisórias de 1 px, sem sombra. Raio de 2 px; chips e botões também.
- Alvo de toque mínimo de 44 px em botões do player.
- Largura máxima do conteúdo: 1120 px. Abaixo de 768 px, uma coluna.

## Foco e movimento

- Foco visível: contorno de 2 px em `accent`, afastado 2 px. Nunca remover.
- Transições de até 120 ms, só em cor. Respeitar `prefers-reduced-motion`.

## Componentes

| Componente | Notas |
|---|---|
| `Readout` | rótulo + valor grande + barra fina de confiança |
| `Chip` | atributo com probabilidade (estilo, gênero, voz) |
| `Stage` | etapas separando → analisando → buscando, com a atual em `accent` |
| `Player` | `<audio>` da FMA com crédito visível, ou iframe do Spotify |
| `ActionBar` | pular, aleatório, favoritar, mais parecidas; atalhos de teclado |
| `Notice` | variantes `info` (relaxado, Spotify fora) e `danger` (falha, reenviar) |
| `FilterDrawer` | tom, gênero, voz, BPM, ano; travar envia `filters.locked`; indica que vale só para o catálogo |
| `Button` | `primary` (âmbar), `ghost` (borda `control`) |

## Telas de referência

1. **Entrada**: enviar arquivo ou gravar ~10 s, com validação de 25 MB e mínimo de 3 s.
2. **Progresso**: as três etapas; a primeira análise pode levar ~20 s ou mais.
3. **Recomendação**: leituras da faixa enviada, uma recomendação por vez, player, explicação e ações.
4. **Filtros e playlist**: gaveta de filtros e exportação, com "não está no Spotify" nas faixas sem
   correspondência.
