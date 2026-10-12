export const statusLabels:Record<string,string>={pending:'待复核',ok:'无问题',handled:'已处置',ignored:'忽略'}
export const riskLabels:Record<string,string>={none:'无风险',low:'低',medium:'中',high:'高',unknown:'无法判定'}
export const targetLabels:Record<string,string>={nickname:'昵称',motto:'个人宣言',team_name:'队名',team_description:'战队简介',application_message:'入队申请留言',article:'文章 / 稿件',tournament_description:'赛事说明',scrim_description:'内战说明',page:'普通页面',image:'图片',comment:'评论'}
export const categoryLabels:Record<string,string>={illegal:'违法违规',porn:'色情低俗',attack:'人身攻击',politics:'政治敏感',scam:'广告与诈骗',game_trade:'游戏违规交易',privacy:'泄露他人隐私',impersonation:'冒充官方',other:'其他可疑'}
export function categories(values:string[]){return values.map(value=>categoryLabels[value]||value).join('、')||'—'}
