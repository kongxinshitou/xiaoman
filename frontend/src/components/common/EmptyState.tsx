import { Empty, Button } from 'antd'
import { PlusOutlined } from '@ant-design/icons'

interface Props {
  description?: string
  onAction?: () => void
  actionText?: string
}

export default function EmptyState({
  description = '暂无数据',
  onAction,
  actionText = '立即添加',
}: Props) {
  return (
    <Empty description={description} image={Empty.PRESENTED_IMAGE_SIMPLE}>
      {onAction && (
        <Button type="primary" icon={<PlusOutlined />} onClick={onAction}>
          {actionText}
        </Button>
      )}
    </Empty>
  )
}
