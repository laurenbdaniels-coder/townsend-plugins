export const isPaidOrder = (order: { status: string }) => order.status === "paid";
