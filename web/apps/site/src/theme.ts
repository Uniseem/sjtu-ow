// Colour mode choices shared by the masthead menu and the phone drawer.
// The head script owns the truth (window.owTheme, localStorage ow-theme);
// this module is only the typed handle the components use.
export type ThemeChoice = "system" | "light" | "dark"

export type OwTheme = {
  current(): ThemeChoice
  set(choice: ThemeChoice): void
}

export function owTheme(): OwTheme | null {
  return typeof window === "undefined" ? null : ((window as { owTheme?: OwTheme }).owTheme ?? null)
}
