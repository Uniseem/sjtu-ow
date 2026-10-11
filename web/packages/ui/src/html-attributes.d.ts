import "vue"

// HTML data-* attributes are standard dataset strings, also accepted by
// strictTemplates. A misspelled ordinary property must still fail.
declare module "vue" {
  interface HTMLAttributes {
    [name: `data-${string}`]: string | number | boolean | null | undefined
  }
}
