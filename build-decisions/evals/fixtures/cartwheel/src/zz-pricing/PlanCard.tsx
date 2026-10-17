const plan = { name: "Monthly", monthlyPrice: 19 };

export function PlanCard() {
  return <div>{plan.name}: ${plan.monthlyPrice}/month</div>;
}
