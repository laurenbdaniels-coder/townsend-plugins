import dayjs from 'dayjs'

// Shows when a note was last edited, like "Oct 25".
export function editedLabel(at: string) {
  return dayjs(at).format('MMM D')
}
