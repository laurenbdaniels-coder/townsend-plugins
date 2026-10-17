// pulled from /api/admin/feedback; the cost/timing aggregates live elsewhere
export function sendFeedback(feedback: string) {
  return post("/api/feedback", feedback);
}
export const chargebackReason = (reason: string) => reason;
