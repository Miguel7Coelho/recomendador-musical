const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });

export const formatBpm = (bpm: number) => decimal.format(bpm);

export const formatPercent = (fraction: number) => `${Math.round(fraction * 100)}%`;

export const formatScore = (score: number) =>
  score.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatKey = (key: string, scale: "major" | "minor") =>
  `${key} ${scale === "major" ? "maior" : "menor"}`;

/** "Electronic---Downtempo" → "Downtempo". */
export const styleName = (style: string) => style.split("---").pop() ?? style;

export function sortedStyles(styles: Record<string, number>): Array<[string, number]> {
  return Object.entries(styles).sort((a, b) => b[1] - a[1]);
}

const WORDS: Record<string, string> = {
  key: "tom",
  genre: "gênero",
  voice: "voz",
  exact: "exato",
  compatible: "compatível",
  off: "desligado",
  style: "estilo",
  on: "ligado",
};

/** "key: exact → compatible" → "tom: exato → compatível". */
export const formatRelaxed = (step: string) =>
  step.replace(/[a-z]+/g, (word) => WORDS[word] ?? word);
