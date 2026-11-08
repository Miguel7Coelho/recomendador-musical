# Design system: recomendador musical

Fonte da verdade do visual. Os valores vivem em `src/index.css`; mudou aqui, muda lá.

## O padrão

**Um único material.** A página inteira é uma só superfície cinza-pérola, e cada elemento ou sai dela
ou afunda nela. Não existe borda, divisória nem segunda cor de fundo.

| Estado | Classe | Onde |
|---|---|---|
| Em relevo | `.panel`, `.btn`, `.round` | cartões, botões: o que se toca ou o que contém |
| Afundado | `.well`, `.field`, `.meter`, `.range` | campos, chips, avisos, barras: o que recebe ou mede |
| Pressionado | `aria-pressed` e `:active` | o botão passa de relevo para afundado |

Tipografia, cor e ritmo vêm da referência da Apple: títulos grandes e justos, centralizados, muito
respiro, uma só cor de ação, botões em pílula.

Antes de criar qualquer coisa nova, ela precisa caber numa linha dessa tabela.

## Movimento

Duas animações, cada uma com um único significado:

- **`.flip-in`**: algo novo chegou à tela (o cartão de uma recomendação, o painel de uma tela).
- **`.halo`**: aqui tem som. Só no botão de gravar, na gravação em curso e no play parado. Ao tocar,
  o halo some e o botão afunda.

O resto são transições de até 220 ms em sombra, cor e posição. `prefers-reduced-motion` desliga as
duas animações.

## Cores

| Token | Valor | Uso |
|---|---|---|
| `surface` | `oklch(0.93 0.008 265)` | a única superfície |
| `shade`, `glow` | derivados de `surface` | as duas sombras do relevo; nunca como cor de fundo |
| `text` | `#1d1d1f` | texto e leituras |
| `muted` | `#5c5d66` | rótulos e texto secundário (AA sobre `surface`) |
| `accent` | `#0066cc` | toda ação, foco e preenchimento de barra |
| `accent-hover` | `#0071e3` | hover do botão principal e contorno de foco |
| `danger` | `#c4321f` | erro e gravação em curso |

Cor nunca é o único sinal: estados também têm texto, ícone ou mudança de relevo.

## Tipografia

**Inter** (variável), com espaçamento levemente negativo, e números em `tabular-nums`. Decimais em
vírgula (pt-BR).

| Token | Tamanho / altura | Uso |
|---|---|---|
| `label` | 11/16, maiúsculas, espaçado | rótulos de leitura e seção |
| `small` | 14/20 | crédito, explicação |
| `body` | 17/25 | texto corrente, controles |
| `lead` | 21/28 | subtítulo, artista |
| `title` | 24/30, 600 | nome da faixa enviada |
| `headline` | 40/44, 600 | nome da recomendação |
| `hero` | até 56, 600 | título da entrada |
| `readout` | 40/44, 600 | tom e BPM |

## Forma

- Raios: painel 28 px, poço 20 px; botões e campos em pílula; ícones em círculo.
- Alvo de toque mínimo de 44 px. `.round` tem 44 px no celular e 52 px acima de 640 px;
  `.round-lg`, 72 e 88 px.
- Largura máxima do conteúdo: 1120 px. Abaixo de 1024 px, uma coluna.
- Foco visível: contorno de 2 px em `accent-hover`. Nunca remover.

## Ícone

O botão do microfone como marca: disco em relevo, dois anéis de halo e, no centro, um círculo
`accent` com três barras brancas de forma de onda. Até 48 px fica só o círculo com as barras, porque
sombra e anéis desaparecem nesse tamanho.

## Evitar

Bordas e divisórias, gradientes decorativos, segunda cor de destaque, vidro fosco, halo em algo que
não emite som, e flip em algo que já estava na tela.

## Componentes

| Componente | Notas |
|---|---|
| `Button` | pílula; `primary` (azul) ou neutra |
| `RoundButton` | só ícone, com `aria-label` e `title`; `large` para a ação central |
| `Readout` | rótulo, valor grande e barra de confiança |
| `Chip` | etiquetas e probabilidades, afundado |
| `Notice` | afundado, `info` ou `danger`; o retorno do login some em 40 s e tem botão de fechar |
| `Player` | controles próprios sobre `<audio>` no catálogo FMA, ou iframe do Spotify/YouTube |
