import { isAllowedRole } from "../lib/accounts";

export function InviteForm({ role }: { role: string }) {
  const valid = isAllowedRole(role);
  return <button disabled={!valid}>Invite</button>;
}
