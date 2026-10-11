// Typed fixtures for SSR tests; never used by production loaders.
import type {GetApiTeamsOut,GetApiTeamsIdOut} from "@sjtu-ow/api"
export const emptyTeams:GetApiTeamsOut={banner_image_id:null,teams:[],team_total:0,recruiting_total:0,role_counts:{tank:0,damage:0,support:0},max_members:10,recruiting_only:false,role:""}
export const emptyTeam:GetApiTeamsIdOut={team:{id:12,name:"夜航",description:"",logo_image_id:null,is_recruiting:true,recruiting_roles:[],version:1,created_at:"2026-10-01T00:00:00Z",updated_at:"2026-10-01T00:00:00Z"},entries:[],members:[],alumni:[],max_members:10,viewer:{is_member:false,is_captain:false,is_superuser:false,can_apply:false,needs_game_account:false,apply_reason:"请先登录。"}}
