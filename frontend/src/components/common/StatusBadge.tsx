import { Badge } from 'antd'

type Status = 'success' | 'error' | 'warning' | 'processing' | 'default'

interface Props {
  status: Status
  text: string
}

export default function StatusBadge({ status, text }: Props) {
  return <Badge status={status} text={text} />
}
