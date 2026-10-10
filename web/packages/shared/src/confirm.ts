// Keep the old native confirmation and wording. Creating the helper is SSR
// safe: window is only read when a browser event invokes the returned function.
export function useConfirm(): (message: string) => boolean {
  return (message) => window.confirm(message)
}
