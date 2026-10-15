import { ROLE_ALLOWLIST } from "../lib/accounts";

export function InviteForm({ role }: { role: string }) {
  const valid = role !== "" && ROLE_ALLOWLIST.includes(role);
  return <button disabled={!valid}>Invite</button>;
}
