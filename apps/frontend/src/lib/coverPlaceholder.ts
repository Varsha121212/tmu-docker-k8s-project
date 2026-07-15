const GRADIENTS = [
  ["#8B6BF0", "#5B3FC0"],
  ["#7A5AC4", "#402A66"],
  ["#6366F1", "#3730A3"],
  ["#C084E8", "#862FAE"],
  ["#7C7BEB", "#4338CA"],
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function getCoverGradient(category: string): string {
  const [from, to] = GRADIENTS[hashString(category) % GRADIENTS.length];
  return `linear-gradient(135deg, ${from}, ${to})`;
}
