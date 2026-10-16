export async function POST(req: Request) {
  const event = await req.json();
  switch (event.type) {
    case "checkout.session.completed":
      await markPaid(event.data.object.customer);
      break;
  }
  return new Response("ok");
}

async function markPaid(customer: string) {}
