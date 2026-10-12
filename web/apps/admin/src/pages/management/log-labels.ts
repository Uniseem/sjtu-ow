const actions: Record<string, string> = {
  create: '新建', update: '修改', delete: '删除', publish: '发布', unpublish: '撤下',
  approve: '通过', reject: '驳回', withdraw: '撤回', dissolve: '撤销报名', disband: '解散战队',
  activate: '启用账号', deactivate: '停用账号', hide: '隐藏评论', unhide: '恢复评论',
  pin: '置顶评论', unpin: '取消置顶', assign_captain: '指定队长', roles: '修改角色',
  feature_rule_add: '添加功能规则', feature_rule_delete: '删除功能规则',
  member_group_add: '加入成员分组', member_group_remove: '移出成员分组',
  member_group_move: '调整分组顺序', member_group_title: '修改组内职务',
  settings_update: '修改全站设置', test_email: '发送测试邮件',
  font_import: '添加字体', font_delete: '删除字体', typography_update: '修改排版',
  registration_approve: '通过报名', registration_reject: '驳回报名', registration_dissolve: '撤销报名',
  article_publish: '发布文章', article_unpublish: '撤下文章', article_update: '保存文章草稿',
  tournament_publish: '发布赛事', tournament_cancel: '取消赛事', tournament_update: '修改赛事',
  scrim_publish: '发布内战', scrim_cancel: '取消内战', scrim_update: '修改内战',
}
const objects: Record<string, string> = { user: '用户', team: '战队', member_group: '成员分组', article: '文章', tournament: '赛事', scrim: '内战', registration: '报名', comment: '评论', settings: '全站设置', font: '字体', typography: '排版设置' }
export function actionLabel(action: string) { return actions[action] ?? actions[action.replaceAll('.', '_')] ?? actions[action.split('.').at(-1) ?? ''] ?? action }
export function objectLabel(type: string) { return objects[type] ?? type }
export function objectHref(type: string, id: number): string | undefined {
  if (!Number.isSafeInteger(id) || id <= 0) return undefined
  const paths: Record<string, string> = { user: `/admin/users/${id}/`, team: `/admin/teams/edit/${id}/`, member_group: `/admin/member-groups/${id}/`, article: `/admin/articles/${id}/`, tournament: `/admin/tournaments/edit/${id}/`, scrim: `/admin/scrims/edit/${id}/`, registration: `/admin/registrations/${id}/`, font: `/admin/fonts/${id}/` }
  return paths[type]
}
