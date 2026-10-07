// The same call on both sides: on the server it goes to the Go API (here a
// mock the Node server answers), in the browser it is the same-origin fetch.
export interface TeamRow { id: number; name: string; members: number; founded: string }
export interface HomeData { title: string; teams: TeamRow[]; now: string }

export async function getHome(base = ""): Promise<HomeData> {
  const response = await fetch(`${base}/api/page/home`);
  return response.json();
}
export async function getTeam(id: string, base = ""): Promise<TeamRow & { description: string }> {
  const response = await fetch(`${base}/api/page/team/${id}`);
  if (!response.ok) throw Object.assign(new Error("not found"), { status: response.status });
  return response.json();
}
