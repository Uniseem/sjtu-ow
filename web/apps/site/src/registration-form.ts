import type { Requester,CallExtras,PostApiTournamentsIdRegistrationsOut,GetApiTournamentsIdOut,GetApiRegistrationsIdOut } from "@sjtu-ow/api"
export type GameChoice={id:number;battletag:string;rank_tank:number|null;rank_damage:number|null;rank_support:number|null}
export type TeamChoice={id:number;name:string;version:number}
export type RegisterMember={user_id:number;nickname:string;is_captain:boolean;is_sjtu:boolean;accounts:GameChoice[];selected_account_id:number|null;problems:string[]}
export type RegisterForm={tournament:GetApiTournamentsIdOut["tournament"];teams:TeamChoice[];team:TeamChoice|null;rows:RegisterMember[];existing:GetApiRegistrationsIdOut["registration"];problems:string[];can_submit:boolean}
export type IndividualForm={tournament:GetApiTournamentsIdOut["tournament"];game_accounts:GameChoice[];my_signup:GetApiTournamentsIdOut["viewer"]["my_signup"];registration_team_name:string;problems:string[];can_submit:boolean;can_cancel:boolean}
// Additive form projections become generated exports at the batch's apigen.
export function getRegisterForm(api:Requester,id:string,team?:number){return api<RegisterForm>("GET","/api/tournaments/{id}/register",{params:{id},query:{team}})}
export function getIndividualForm(api:Requester,id:string){return api<IndividualForm>("GET","/api/tournaments/{id}/signup",{params:{id}})}
export function selectedAccounts(rows:RegisterMember[]):Record<string,number>{
 const selected:Record<string,number>={}
 for(const row of rows){const candidate=row.selected_account_id||row.accounts[0]?.id;if(candidate)selected[String(row.user_id)]=candidate}
 return selected
}
export function safeRosterSelection(rows:RegisterMember[],values:Record<string,number>):Record<string,number>{
 const selected:Record<string,number>={}
 for(const row of rows){const id=values[String(row.user_id)];if(row.accounts.some(account=>account.id===id))selected[String(row.user_id)]=id}
 return selected
}

export function submitRegisterForm(api:Requester,id:number,body:{team_id:number;accounts:Record<string,number>;base_team_version:number;base_roster_version:number},extras:CallExtras){return api<PostApiTournamentsIdRegistrationsOut>("POST","/api/tournaments/{id}/registrations",{...extras,params:{id},body})}
