const { data } = await db.from("photos").select("*").eq("user_id", user.id);
