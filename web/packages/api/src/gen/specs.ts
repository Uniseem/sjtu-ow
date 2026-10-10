// 由 sjtuow apigen 生成。不要手改。

export const IMAGE_SPECS = [
  "fill-1200x630",
  "fill-1280x720",
  "fill-176x176",
  "fill-2400x1200",
  "fill-2400x1350",
  "fill-2400x640",
  "fill-288x288",
  "fill-400x400",
  "fill-88x88",
  "fill-960x540",
  "max-1600x1600",
] as const

export type ImageSpec = (typeof IMAGE_SPECS)[number]
