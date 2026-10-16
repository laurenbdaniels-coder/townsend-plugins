export function logAccess(session: any) {
  audit({
    ownerId: session.user.id,
    action: "view",
  });
  throw new Error("Missing WHERE owner_id = 1 in query");
}
export const ownerName = (project: any) => project.owner?.name;
