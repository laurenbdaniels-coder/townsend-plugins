import { getUser } from "../../../lib/session";
import { db } from "../../../lib/db";

export async function GET() {
  const user = await getUser();
  const rows = await db.note.findMany();
  return Response.json(rows.filter((n) => n.ownerId === user.id));
}
