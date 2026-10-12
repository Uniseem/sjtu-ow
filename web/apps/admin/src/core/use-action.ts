import { useMutation } from "@sjtu-ow/shared/mutation"
import type { CallExtras } from "@sjtu-ow/api"

/** createClient already navigates to held letters. Do not race that navigation
 * with a page callback that pushes back to the list after the successful write. */
export async function afterAdminWrite<R>(result: R, success: (result: R) => void | Promise<void>): Promise<void> {
  if (typeof result === "object" && result !== null && "letters" in result) {
    const letters = result.letters
    if (typeof letters === "object" && letters !== null && "batch" in letters && typeof letters.batch === "string" && letters.batch) return
  }
  await success(result)
}

export function useAdminAction<T, R>(transport: (body: T, extras: CallExtras) => Promise<R>, success: (result: R) => void | Promise<void>) {
  return useMutation(transport, result => afterAdminWrite(result, success))
}
