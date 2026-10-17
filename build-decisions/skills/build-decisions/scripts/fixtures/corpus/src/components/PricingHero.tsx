export function PricingHero() {
  const label = "Total price - billed monthly";
  return (
    <section className="price-tag text-lg total-banner">
      <h1>Simple pricing for everyone</h1>
      <p>{label}</p>
      <p>Total price - billed monthly, cancel any time</p>
    </section>
  );
}
