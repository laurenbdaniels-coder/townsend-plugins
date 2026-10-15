export function canEditAnything(user: { role: string }) {
  if (user.role === "admin") {
    return true;
  }
  return false;
}
