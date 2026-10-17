const { data } = await db.from("files").select("*").eq("account_id", account.id);
