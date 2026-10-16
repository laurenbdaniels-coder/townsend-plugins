const { data } = await db.from("reports").select("*").eq("owner_id", user.id);
