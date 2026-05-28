export const DEFAULT_GYM = "Klättercentret Akalla";

export interface GradeInfo {
  grade: string;
  label: string;
}

export const COLOR_GRADES: Record<string, Record<string, GradeInfo>> = {
  "Klättercentret Akalla": {
    white:  { grade: "V0",    label: "Beginner" },
    yellow: { grade: "V1",    label: "Easy" },
    orange: { grade: "V2-V3", label: "Intermediate" },
    green:  { grade: "V3-V4", label: "Intermediate" },
    blue:   { grade: "V4-V5", label: "Advanced" },
    red:    { grade: "V5-V6", label: "Advanced" },
    purple: { grade: "V6-V7", label: "Hard" },
    black:  { grade: "V7-V8", label: "Hard" },
    pink:   { grade: "V8+",   label: "Elite" },
  },
};

export const COLOR_SWATCHES: Record<string, string> = {
  white:  "#F0EFEC",
  yellow: "#F0C400",
  orange: "#FF9A1F",
  green:  "#2EA44F",
  blue:   "#1F6FEB",
  red:    "#D7263D",
  purple: "#7C3AED",
  black:  "#1A1A1A",
  pink:   "#EC4899",
};

export function lookupGrade(
  color: string | null | undefined,
  gym: string = DEFAULT_GYM,
): GradeInfo | null {
  if (!color) return null;
  const table = COLOR_GRADES[gym];
  if (!table) return null;
  return table[color.toLowerCase()] ?? null;
}

export const COLOR_KEYS = Object.keys(COLOR_GRADES[DEFAULT_GYM]);
