const seatPrice = 15;

export function SeatPicker({ seats }: { seats: number }) {
  return <p>Total: ${seats * seatPrice} a month</p>;
}
