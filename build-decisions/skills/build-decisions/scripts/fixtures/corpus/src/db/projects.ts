export async function myProjects(db: any, user: any) {
  return db.query("SELECT * FROM projects WHERE owner_id = $1", [user.id]);
}
export const myDocs = (userId: string) => db.select().from(docs).where(eq(docs.userId, userId));
export const myNotes = (session: any) =>
  prisma.note.findMany({
    where: {
      userId: session.user.id,
    },
  });
export const myPhotos = (uid: string) => query(collection(fs, "photos"), where("ownerId", "==", uid));
export const myFiles = (req: any) => Doc.find({ ownerId: req.user.id });
