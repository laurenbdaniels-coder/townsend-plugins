const { data } = await db.from("invoices").select("*").eq("owner_id", user.id);
