const plans = [
  { name: "Pro", price: 29, interval: "month" },
];

export function PlanCard() {
  return <div className="plan-card">{plans[0].name}</div>;
}
