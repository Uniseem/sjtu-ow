import { ref } from "vue"
import { postApiAdminFontsUploads, postApiAdminFontsUploadsIdChunks, type CallExtras, type PostApiAdminFontsUploadsOut } from "@sjtu-ow/api"
import { useAdminAction } from "../../core/use-action"
import { useAdminApi } from "../../core/api"
import { importFont, type FontDetail } from "./pending"

type Upload = PostApiAdminFontsUploadsOut
type Plan = { beginKey: string; session: Upload | null; chunkKeys: Map<number, string>; sent: number }
export function useFontUpload(success: (result: FontDetail) => void | Promise<void>, familyID = 0) {
  const api = useAdminApi()
  const progress = ref(0)
  const stage = ref("")
  const plans = new Map<string, Plan>()
  const action = useAdminAction<{ file: File; license: boolean }, FontDetail>(async (body, extras) => {
    if (!body.license) throw new Error('请确认字体允许在本站使用。')
    if (body.file.size < 1 || body.file.size > 64 * 1024 * 1024) throw new Error('成品包大小不正确，最大64MB。')
    if (!extras.key) throw new Error('上传缺少请求编号。')
    let plan = plans.get(extras.key)
    if (!plan) { plan = { beginKey: crypto.randomUUID(), session: null, chunkKeys: new Map(), sent: 0 }; plans.set(extras.key, plan) }
    const active = plan
    function options(key: string): CallExtras { return { ...extras, key } }
    if (!active.session) {
      stage.value = '正在建立上传记录…'
      active.session = await postApiAdminFontsUploads(api, { name: body.file.name, total_bytes: body.file.size, license_confirmed: true }, options(active.beginKey))
    }
    const session = active.session
    if (session.chunk_size < 1 || session.chunk_size > 128 * 1024 || session.total_bytes !== body.file.size) throw new Error('上传记录与文件不一致。')
    while (active.sent < body.file.size) {
      stage.value = '正在上传成品包…'
      const offset = active.sent
      const part = new Uint8Array(await body.file.slice(offset, Math.min(body.file.size, offset + session.chunk_size)).arrayBuffer())
      let binary = ''
      for (let index = 0; index < part.length; index += 32768) binary += String.fromCharCode(...part.subarray(index, index + 32768))
      let key = active.chunkKeys.get(offset)
      if (!key) { key = crypto.randomUUID(); active.chunkKeys.set(offset, key) }
      await postApiAdminFontsUploadsIdChunks(api, session.id, { offset, data_base64: btoa(binary) }, options(key))
      active.sent += part.length
      progress.value = Math.floor(active.sent / body.file.size * 100)
    }
    stage.value = '正在核查清单和字体分片…'
    const result = await importFont(api, { source: 'package', family_id: familyID || undefined, package_name: body.file.name, upload_id: session.id, license_confirmed: true }, extras)
    plans.delete(extras.key)
    stage.value = '已上传。'
    return result
  }, success)
  return { ...action, progress, stage }
}
