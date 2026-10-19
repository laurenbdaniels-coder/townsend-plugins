'use client'
import { collection, addDoc, getFirestore } from 'firebase/firestore'
const db = getFirestore()
export function StartCheckout({ uid, priceId }: { uid: string; priceId: string }) {
  const go = async () => {
    await addDoc(collection(db, 'customers', uid, 'checkout_sessions'), {
      price: priceId,
      success_url: window.location.origin,
    })
  }
  return <button onClick={go}>Upgrade</button>
}
