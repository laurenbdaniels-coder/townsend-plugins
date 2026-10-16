"use client";
import { useState } from "react";

export default function Projects({ initial }: { initial: { id: string; name: string }[] }) {
  const [projects, setProjects] = useState(initial);

  async function remove(id: string) {
    const res = await fetch(`/api/projects/${id}`, { method: "DELETE" });
    if (res.ok) setProjects((p) => p.filter((x) => x.id !== id));
  }

  async function addTask(projectId: string, title: string) {
    await fetch("/api/tasks", { method: "POST", body: JSON.stringify({ projectId, title }) });
  }

  return (
    <ul>
      {projects.map((p) => (
        <li key={p.id}>
          {p.name} <button onClick={() => remove(p.id)}>Delete</button>
          <button onClick={() => addTask(p.id, "New task")}>Add task</button>
        </li>
      ))}
    </ul>
  );
}
