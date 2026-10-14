const { data } = await db.from("tags").select("*").eq("org_id", org.id);
