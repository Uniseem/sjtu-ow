import type { CollectionNode } from "./pending"

export type CollectionRow = { node: CollectionNode; depth: number; path: string; orphaned: boolean }

/** Preserve siblings' server ordering; cycles and missing parents remain visible. */
export function collectionRows(nodes: CollectionNode[]): CollectionRow[] {
  const rows: CollectionRow[] = []
  const children = new Map<number | null, CollectionNode[]>()
  const seen = new Set<number>()
  const all = new Set(nodes.map((node) => node.id))
  for (const node of nodes) {
    const parent = node.parent_id ?? null
    const group = children.get(parent) ?? []
    group.push(node)
    children.set(parent, group)
  }
  function visit(node: CollectionNode, depth: number, path: string, orphaned: boolean): void {
    if (seen.has(node.id)) return
    seen.add(node.id)
    const fullPath = path ? `${path} / ${node.name}` : node.name
    rows.push({ node, depth, path: fullPath, orphaned })
    for (const child of children.get(node.id) ?? []) visit(child, depth + 1, fullPath, orphaned)
  }
  for (const root of children.get(null) ?? []) visit(root, 0, "", false)
  for (const node of nodes) {
    if (!seen.has(node.id) && (node.parent_id === null || !all.has(node.parent_id))) visit(node, 0, "", true)
  }
  for (const node of nodes) {
    if (!seen.has(node.id)) visit(node, 0, "", true)
  }
  return rows
}

export function hasCollectionChildren(id: number, nodes: CollectionNode[]): boolean {
  return nodes.some((node) => node.parent_id === id)
}
