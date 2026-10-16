export const PLAN_ALLOWLIST = ["free", "pro", "team"];
export const ROLE_ALLOWLIST = ["member", "admin"];

export function isAllowedRole(role: string | null): boolean {
  return role !== null && ROLE_ALLOWLIST.includes(role);
}
