import { Select, Tag } from 'antd'
import type { LLMProvider } from '../../types/llm'

interface Props {
  providers: LLMProvider[]
  value?: string | null
  onChange?: (id: string | null) => void
  placeholder?: string
  size?: 'small' | 'middle' | 'large'
  style?: React.CSSProperties
}

export default function ModelSelector({
  providers,
  value,
  onChange,
  placeholder = '选择模型',
  size = 'middle',
  style,
}: Props) {
  const options = providers
    .filter((p) => p.is_active)
    .map((p) => ({
      value: p.id,
      label: (
        <span>
          {p.name}
          <Tag color="blue" style={{ marginLeft: 6, fontSize: 10 }}>
            {p.model_name}
          </Tag>
          {p.is_default && (
            <Tag color="purple" style={{ fontSize: 10 }}>
              默认
            </Tag>
          )}
        </span>
      ),
    }))

  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      placeholder={placeholder}
      allowClear
      size={size}
      style={style}
    />
  )
}
