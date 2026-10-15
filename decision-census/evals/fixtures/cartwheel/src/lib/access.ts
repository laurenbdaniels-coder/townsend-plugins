import type { User } from "./types";

export function canUseReports(user: User): boolean {
  if (user.subscription?.status === "active") {
    return true;
  }
  return false;
}
