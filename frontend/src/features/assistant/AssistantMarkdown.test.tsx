import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { AssistantMarkdown } from './AssistantMarkdown'

test('renders readable headings, emphasis and GFM tables', () => {
  render(<AssistantMarkdown content={'## 风险结果\n\n**设备**：DEMO-AGM-001\n\n| 时间窗口 | 风险 |\n| --- | --- |\n| 30 天 | 0.28 |'} dataProfile="demo" />)

  expect(screen.getByRole('heading', { level: 2, name: '风险结果' })).toBeInTheDocument()
  expect(screen.getByRole('strong')).toHaveTextContent('设备')
  expect(screen.getByRole('table')).toBeInTheDocument()
  expect(screen.getByRole('region', { name: '可横向滚动的表格' })).toHaveAttribute('tabindex', '0')
  expect(screen.getByRole('cell', { name: '30 天' })).toBeInTheDocument()
})

test('does not render raw HTML or fetch Markdown images', () => {
  const { container } = render(<AssistantMarkdown content={'安全文本\n\n<img src="https://example.invalid/pixel.png" onerror="alert(1)">\n\n![外部图片](https://example.invalid/image.png)'} dataProfile="production" />)

  expect(container.querySelector('img, script, svg')).toBeNull()
  expect(container).not.toHaveTextContent('onerror')
  expect(screen.getByText('外部图片')).toBeInTheDocument()
})

test('labels mapped demo device references while retaining IDs and link targets', () => {
  render(<AssistantMarkdown content={'核对 DEMO-AGM-018。\n\n[设备 DEMO-AGM-018](/devices/DEMO-AGM-018)'} dataProfile="demo" />)
  expect(screen.getAllByText('月港站闸机 03')).toHaveLength(2)
  expect(screen.getAllByText('设备编号 DEMO-AGM-018')).toHaveLength(2)
  expect(screen.getByRole('link', { name: /月港站闸机 03/ })).toHaveAttribute('href', '/devices/DEMO-AGM-018')
})

test('keeps production assistant references literal', () => {
  const { container } = render(<AssistantMarkdown content="核对 DEMO-AGM-018。" dataProfile="production" />)
  expect(container).toHaveTextContent('核对 DEMO-AGM-018。')
  expect(container).not.toHaveTextContent('月港站闸机 03')
})
