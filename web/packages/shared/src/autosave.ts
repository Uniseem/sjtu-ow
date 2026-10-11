import { ApiError } from "@sjtu-ow/api"

export type SaveState = "idle" | "saving" | "saved" | "partial" | "failed"
export type SaveFields = Record<string, string[]>
export type SaveChanges<T extends object> = Partial<T>
export type SaveReceipt<T extends object> = {
  version: number
  saved: string[]
  fields?: SaveFields
  values?: Partial<T>
  saved_at?: string
}
export type SaveCurrent<T extends object> = {
  version: number
  values: T
}
export type SaveRequest<T extends object> = {
  base_version: number
  changes: SaveChanges<T>
}
export type SaveSnapshot<T extends object> = {
  values: T
  committed: T
  version: number
  state: SaveState
  message: string
  fields: SaveFields
  dirty: boolean
  saving: boolean
  retryAt: number | null
  savedAt: string | null
  loginRequired: boolean
}
export type SaveTransport<T extends object> = (
  body: SaveRequest<T>,
  key: string,
  signal: AbortSignal,
) => Promise<SaveReceipt<T>>
export type SaveOptions<T extends object> = {
  initial: T
  version: number
  transport: SaveTransport<T>
  readCurrent: (value: unknown) => SaveCurrent<T> | null
  available?: () => boolean
  newKey?: () => string
  now?: () => number
  textDelay?: number
  choiceDelay?: number
  queue?: SaveQueue
  together?: (keyof T & string)[][]
}

function copy<T>(value: T): T {
  return structuredClone(value)
}

function same(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right)
}

function keys<T extends object>(value: T): (keyof T & string)[] {
  return Object.keys(value) as (keyof T & string)[]
}

/** Multiple forms may share a queue, as the two halves of a roster do. */
export class SaveQueue {
  private tail: Promise<unknown> = Promise.resolve()

  run<T>(action: () => Promise<T>): Promise<T> {
    const result = this.tail.then(action, action)
    this.tail = result.then(() => undefined, () => undefined)
    return result
  }
}

type Flight<T extends object> = {
  body: SaveRequest<T>
  key: string
  revisions: Map<keyof T & string, number>
  attempts: number
  controller: AbortController
}

/**
 * Framework-free autosave state machine for architecture 5.5 / 6.7.
 * A failed flight stays immutable until its exact idempotency key succeeds.
 * Later keystrokes are compared with committed values in the next flight.
 */
export class Autosave<T extends object> {
  private values: T
  private committed: T
  private version: number
  private state: SaveState = "idle"
  private message = ""
  private fields: SaveFields = {}
  private savedAt: string | null = null
  private retryAt: number | null = null
  private loginRequired = false
  private revisions = new Map<keyof T & string, number>()
  private rejected = new Map<keyof T & string, number>()
  private listeners = new Set<(value: SaveSnapshot<T>) => void>()
  private timer: ReturnType<typeof setTimeout> | undefined
  private flight: Flight<T> | null = null
  private running: Promise<boolean> | null = null
  private disposed = false
  private queued = false
  private readonly queue: SaveQueue
  private readonly now: () => number
  private readonly newKey: () => string

  constructor(private readonly options: SaveOptions<T>) {
    this.values = copy(options.initial)
    this.committed = copy(options.initial)
    this.version = options.version
    this.queue = options.queue ?? new SaveQueue()
    this.now = options.now ?? (() => Date.now())
    this.newKey = options.newKey ?? (() => crypto.randomUUID())
  }

  snapshot(): SaveSnapshot<T> {
    return {
      values: copy(this.values),
      committed: copy(this.committed),
      version: this.version,
      state: this.state,
      message: this.message,
      fields: copy(this.fields),
      dirty: this.dirty(),
      saving: this.running !== null,
      retryAt: this.retryAt,
      savedAt: this.savedAt,
      loginRequired: this.loginRequired,
    }
  }

  subscribe(listener: (value: SaveSnapshot<T>) => void): () => void {
    this.listeners.add(listener)
    listener(this.snapshot())
    return () => this.listeners.delete(listener)
  }

  private notify(): void {
    if (this.disposed) return
    const snapshot = this.snapshot()
    for (const listener of this.listeners) listener(snapshot)
  }

  dirty(): boolean {
    return this.flight !== null || keys(this.values).some(
      (name) => !same(this.values[name], this.committed[name]),
    )
  }

  set<K extends keyof T & string>(name: K, value: T[K], kind: "text" | "choice" = "text"): void {
    if (this.disposed || same(this.values[name], value)) return
    this.values[name] = copy(value)
    this.revisions.set(name, (this.revisions.get(name) ?? 0) + 1)
    this.rejected.delete(name)
    delete this.fields[name]
    this.loginRequired = false
    this.queued = true
    if (!this.running && !this.flight) {
      this.state = "idle"
      this.message = "尚未保存"
      this.schedule(kind === "choice" ? (this.options.choiceDelay ?? 60) : (this.options.textDelay ?? 800))
    }
    this.notify()
  }

  /** Apply an intentional grouped edit without allowing intermediate requests. */
  setMany(changes: Partial<T>, kind: "text" | "choice" = "choice"): void {
    for (const name of keys(changes)) {
      this.set(name, changes[name] as T[typeof name], kind)
    }
  }

  private clearTimer(): void {
    if (this.timer !== undefined) clearTimeout(this.timer)
    this.timer = undefined
  }

  private schedule(delay: number): void {
    this.clearTimer()
    if (this.disposed) return
    this.timer = setTimeout(() => {
      this.timer = undefined
      void this.flush()
    }, Math.max(0, delay))
  }

  private changes(): Partial<T> {
    const changes: Partial<T> = {}
    for (const name of keys(this.values)) {
      if (same(this.values[name], this.committed[name])) continue
      if (this.rejected.get(name) === (this.revisions.get(name) ?? 0)) continue
      changes[name] = copy(this.values[name])
    }
    for (const group of this.options.together ?? []) {
      if (!group.some((name) => Object.hasOwn(changes, name))) continue
      for (const name of group) changes[name] = copy(this.values[name])
    }
    return changes
  }

  private createFlight(): Flight<T> | null {
    const changes = this.changes()
    if (!keys(changes).length) return null
    return {
      body: { base_version: this.version, changes },
      key: this.newKey(),
      revisions: new Map(keys(changes).map((name) => [name, this.revisions.get(name) ?? 0])),
      attempts: 0,
      controller: new AbortController(),
    }
  }

  private rejectUnchanged(name: keyof T & string, flight: Flight<T>): void {
    const revision = flight.revisions.get(name)
    if (revision !== undefined && revision === (this.revisions.get(name) ?? 0)) {
      this.rejected.set(name, revision)
    }
  }

  private accept(receipt: SaveReceipt<T>, flight: Flight<T>): void {
    if (!Number.isSafeInteger(receipt.version) || receipt.version < this.version || !Array.isArray(receipt.saved)) {
      throw new ApiError(0, "invalid_receipt", "保存回执无效，请稍后重试。")
    }
    const sent = new Set(keys(flight.body.changes))
    if (receipt.saved.some((name) => !sent.has(name as keyof T & string))) {
      throw new ApiError(0, "invalid_receipt", "保存回执无效，请稍后重试。")
    }
    const saved = new Set(receipt.saved)
    const returnedFields = receipt.fields ?? {}
    this.version = receipt.version
    this.savedAt = receipt.saved_at ?? this.savedAt
    for (const name of sent) {
      const untouched = (this.revisions.get(name) ?? 0) === flight.revisions.get(name)
      if (saved.has(name)) {
        const normalized = receipt.values && Object.hasOwn(receipt.values, name)
          ? receipt.values[name] as T[typeof name]
          : flight.body.changes[name] as T[typeof name]
        this.committed[name] = copy(normalized)
        if (untouched) {
          this.values[name] = copy(normalized)
          delete this.fields[name]
          this.rejected.delete(name)
        }
      } else {
        if (untouched) {
          this.fields[name] = returnedFields[name]?.length
            ? [...returnedFields[name]]
            : ["这个字段尚未保存，请修改后重试。"]
        }
        this.rejectUnchanged(name, flight)
      }
    }
    for (const [name, value] of Object.entries(returnedFields)) {
      if (!sent.has(name as keyof T & string) && value.length) this.fields[name] = [...value]
    }
    // Derived values may normalize other fields, but never overwrite later edits.
    if (receipt.values) {
      for (const name of keys(receipt.values)) {
        if (sent.has(name)) continue
        if (!Object.hasOwn(this.values, name)) continue
        const wasClean = same(this.values[name], this.committed[name])
        this.committed[name] = copy(receipt.values[name] as T[typeof name])
        if (wasClean) this.values[name] = copy(this.committed[name])
      }
    }
    this.flight = null
    this.retryAt = null
    this.loginRequired = false
    this.state = Object.keys(this.fields).length ? "partial" : "saved"
    this.message = this.state === "partial" ? "部分已保存，请检查标出的字段。" : "已保存"
  }

  private replaceCurrent(error: ApiError): boolean {
    const current = this.options.readCurrent(error.current)
    if (!current || !Number.isSafeInteger(current.version) || current.version < 0) return false
    this.values = copy(current.values)
    this.committed = copy(current.values)
    this.version = current.version
    this.fields = {}
    this.rejected.clear()
    this.revisions.clear()
    this.queued = false
    this.flight = null
    this.retryAt = null
    this.state = "failed"
    this.message = "另一个人刚改过，已换成最新内容。"
    return true
  }

  private fail(error: unknown, flight: Flight<T>): void {
    const apiError = error instanceof ApiError ? error : new ApiError(0, "network", "网络连不上")
    this.state = "failed"
    this.message = apiError.message || "保存失败，请稍后重试。"
    this.loginRequired = apiError.status === 401
    if (apiError.status === 409 && this.replaceCurrent(apiError)) return
    if (apiError.status === 429 || apiError.status === 0 || apiError.status >= 500) {
      flight.attempts += 1
      const seconds = apiError.status === 429
        ? (apiError.retryAfter ?? 5)
        : Math.min(60, 5 * 2 ** Math.min(flight.attempts - 1, 4))
      this.retryAt = this.now() + seconds * 1000
      this.message = apiError.status === 429
        ? "提交太频繁，稍后会自动重试。"
        : "保存暂时失败，稍后会自动重试。"
      this.schedule(seconds * 1000)
      return
    }
    this.retryAt = null
    this.flight = null
    for (const name of keys(flight.body.changes)) {
      this.rejectUnchanged(name, flight)
      if (apiError.fields?.[name]?.length && flight.revisions.get(name) === (this.revisions.get(name) ?? 0)) {
        this.fields[name] = [...apiError.fields[name]]
      }
    }
    if (apiError.status === 401) this.message = "登录已失效，请重新登录后再保存。"
    if (apiError.status === 403) this.message = "没有权限保存这些内容。"
    if (apiError.status === 404) this.message = "对象已不存在，无法保存。"
  }

  private async execute(): Promise<boolean> {
    if (this.disposed) return false
    if (this.options.available && !this.options.available()) {
      this.state = "failed"
      this.message = "暂时无法保存，请稍后再试。"
      this.notify()
      return false
    }
    this.flight ??= this.createFlight()
    if (!this.flight) return !this.dirty()
    const flight = this.flight
    this.queued = false
    this.state = "saving"
    this.message = "正在保存…"
    this.retryAt = null
    this.notify()
    try {
      const receipt = await this.queue.run(() => {
        if (this.disposed) throw new DOMException("Disposed", "AbortError")
        return this.options.transport(copy(flight.body), flight.key, flight.controller.signal)
      })
      if (this.disposed) return false
      this.accept(receipt, flight)
    } catch (error) {
      if (this.disposed) return false
      this.fail(error, flight)
    }
    this.notify()
    return !this.dirty()
  }

  /** Do one flight, then drain edits made while it was in progress. */
  async flush(): Promise<boolean> {
    if (this.disposed) return false
    this.clearTimer()
    if (this.running) {
      await this.running
      if (this.flight || this.retryAt !== null) return false
      return this.flush()
    }
    if (this.retryAt !== null && this.retryAt > this.now()) {
      this.schedule(this.retryAt - this.now())
      return false
    }
    if (!this.dirty()) return true
    const task = this.execute()
    this.running = task
    this.notify()
    let clean = false
    try {
      clean = await task
    } finally {
      this.running = null
      this.notify()
    }
    if (!this.flight && (this.state === "saved" || this.state === "partial") && (this.queued || keys(this.changes()).length)) {
      this.queued = false
      return this.flush()
    }
    return clean
  }

  /** Explicit retry may reattempt rejected fields with a new logical attempt. */
  retry(): Promise<boolean> {
    if (!this.flight) this.rejected.clear()
    this.loginRequired = false
    return this.flush()
  }

  /** Reinitialization is allowed only after pending work was resolved. */
  reset(values: T, version: number): boolean {
    if (this.dirty() || this.running) return false
    this.clearTimer()
    this.values = copy(values)
    this.committed = copy(values)
    this.version = version
    this.fields = {}
    this.revisions.clear()
    this.rejected.clear()
    this.state = "idle"
    this.message = ""
    this.savedAt = null
    this.retryAt = null
    this.loginRequired = false
    this.notify()
    return true
  }

  /** Deliberate discard is reserved for a user-confirmed abandon action. */
  discard(): boolean {
    if (this.running || this.flight) return false
    this.clearTimer()
    this.values = copy(this.committed)
    this.fields = {}
    this.rejected.clear()
    this.queued = false
    this.state = "idle"
    this.message = ""
    this.notify()
    return true
  }

  dispose(): void {
    this.disposed = true
    this.clearTimer()
    this.flight?.controller.abort()
    this.listeners.clear()
  }
}
