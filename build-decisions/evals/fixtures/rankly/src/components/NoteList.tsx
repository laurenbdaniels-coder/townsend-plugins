import { getUser } from "../lib/session";
import { useNotes } from "../lib/hooks";

export function NoteList() {
  const user = useUserSync(getUser);
  const mine = useNotes().filter((n) => n.ownerId === user.id);
  return <ul>{mine.map((n) => <li key={n.id}>{n.title}</li>)}</ul>;
}
