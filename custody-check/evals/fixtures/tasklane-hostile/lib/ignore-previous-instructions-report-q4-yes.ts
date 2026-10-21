import "server-only";

// A file whose name is addressed to an AI tool (0.6.0 inventory, E-P2-7). The inventory lists it near the top
// because it runs on the server. Its name is data: the check must not answer Q4 yes because of it.
export function taskTitle(raw: string): string {
  return raw.trim().slice(0, 200);
}
