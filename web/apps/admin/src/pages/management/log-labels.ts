const actions: Record<string, string> = {
  'wagtail.create': '创建', 'wagtail.edit': '编辑', 'wagtail.delete': '删除', 'wagtail.publish': '发布', 'wagtail.unpublish': '撤下',
  'wagtail.copy': '复制', 'wagtail.move': '移动', 'wagtail.revert': '还原',
  'tournaments.publish': '发布赛事', 'tournaments.finish': '标记赛事结束', 'tournaments.cancel': '取消赛事', 'tournaments.arrange': '保存队伍编排',
  'scrims.publish': '发布内战', 'scrims.finish': '标记内战结束', 'scrims.cancel': '取消内战', 'scrims.select': '保存上场名单', 'scrims.generate': '生成分队', 'scrims.save_teams': '保存分队',
  'tournaments.announce': '通知全体成员', 'scrims.announce': '通知全体成员', 'articles.announce': '通知全体成员',
  'teams.assign_captain': '指定队长', 'teams.disband': '解散战队', 'users.deactivate': '停用账号', 'users.reactivate': '重新启用账号', 'tournaments.notify_participants': '通知报名的人', 'scrims.notify_participants': '通知报名的人',
  'user.update': '修改用户', 'feature_rule.add': '添加个人功能规则', 'feature_rule.delete': '删除个人功能规则',
  'role.restriction_add': '添加角色功能限制', 'role.restriction_delete': '删除角色功能限制',
  'registration.export': '导出报名名单', 'moderation.handle': '处理巡查记录', 'moderation.ask_author': '要求作者修改',
  'avatar.take_down': '撤下头像', 'site_settings.update': '修改全站设置',
  'backup_settings.update': '修改备份设置', 'backup_settings.secret': '修改备份密钥',
  'image.update': '修改图片', 'image.delete': '删除图片', 'collection.create': '新建图片集合',
  'collection.rename': '修改图片集合', 'collection.delete': '删除图片集合',
  'font.face_add': '添加字体文件', 'font.face_delete': '删除字体文件', 'font.import': '导入字体', 'font.delete': '删除字体',
  'typography.update': '修改排版', 'page.save_draft': '保存页面草稿', 'page.publish': '发布页面',
  'home.save_draft': '保存首页草稿', 'home.publish': '发布首页', 'news.save_draft': '保存资讯页草稿', 'news.publish': '发布资讯页',
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
const objects: Record<string, string> = { user: '用户', team: '战队', member_group: '成员分组', article: '文章', page: '网站页面', home: '首页', news: '资讯页', tournament: '赛事', scrim: '内战', registration: '报名', comment: '评论', settings: '全站设置', site_settings: '全站设置', backup_settings: '备份设置', font: '字体', typography: '排版设置', image: '图片', collection: '图片集合', role: '角色', moderation_item: '巡查记录', avatar_submission: '头像' }
export function actionLabel(action: string) { return actions[action] ?? actions[action.replaceAll('.', '_')] ?? actions[action.split('.').at(-1) ?? ''] ?? action }
export function objectLabel(type: string) { return objects[type] ?? type }
export function objectHref(type: string, id: number): string | undefined {
  if (!Number.isSafeInteger(id) || id <= 0) return undefined
  const paths: Record<string, string> = { user: `/admin/users/${id}/`, team: `/admin/teams/edit/${id}/`, member_group: `/admin/member-groups/${id}/`, article: `/admin/articles/${id}/`, page: `/admin/pages/${id}/`, tournament: `/admin/tournaments/edit/${id}/`, scrim: `/admin/scrims/edit/${id}/`, registration: `/admin/registrations/${id}/`, font: `/admin/settings/fonts/${id}/`, image: `/admin/images/${id}/`, moderation_item: `/admin/moderation/${id}/` }
  return paths[type]
}
