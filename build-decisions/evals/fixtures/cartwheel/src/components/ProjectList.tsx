"use client";
import { useProjects, useUser } from "../lib/hooks";

export function ProjectList() {
  const user = useUser();
  const projects = useProjects();
  const visible = projects.filter((p) => p.ownerId === user.id || p.shared);
  return <ul>{visible.map((p) => <li key={p.id}>{p.name}</li>)}</ul>;
}
