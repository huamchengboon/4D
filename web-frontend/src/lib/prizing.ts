/** 4D prize RM per RM1 stake (Big / Small). Same as prizing page. */
export const TABLE_4D: { prize: string; big: string; small: string }[] = [
  { prize: "1st", big: "2,500", small: "3,500" },
  { prize: "2nd", big: "1,000", small: "2,000" },
  { prize: "3rd", big: "500", small: "1,000" },
  { prize: "Special", big: "180", small: "—" },
  { prize: "Consolation", big: "60", small: "—" },
];

/** 3D prize RM per RM1 stake (Big / Small). */
export const TABLE_3D: { prize: string; big: string; small: string }[] = [
  { prize: "1st", big: "250", small: "660" },
  { prize: "2nd", big: "210", small: "—" },
  { prize: "3rd", big: "150", small: "—" },
];

function parsePrizeRm(s: string): number {
  if (!s || s === "—") return 0;
  const n = parseInt(s.replace(/,/g, ""), 10);
  return Number.isNaN(n) ? 0 : n;
}

/** Get 4D prize RM for a prize type (1st, 2nd, 3rd, Special, Consolation) and Big vs Small. */
export function get4DPrizeRm(prizeType: string, small: boolean): number {
  const row = TABLE_4D.find((r) => r.prize === prizeType);
  if (!row) return 0;
  return parsePrizeRm(small ? row.small : row.big);
}

/** Get 3D prize RM for 1st/2nd/3rd and Big vs Small. */
export function get3DPrizeRm(prizeType: "1st" | "2nd" | "3rd", small: boolean): number {
  const row = TABLE_3D.find((r) => r.prize === prizeType || r.prize.startsWith(prizeType));
  if (!row) return 0;
  return parsePrizeRm(small ? row.small : row.big);
}
