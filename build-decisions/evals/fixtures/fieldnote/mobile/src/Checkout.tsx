import { Text } from 'react-native'

export function Checkout({ seats }: { seats: number }) {
  const total = seats * 12
  return <Text>Total: ${total}</Text>
}
