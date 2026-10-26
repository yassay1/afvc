import { cloneElement, isValidElement, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { DataProfile } from '../../shared/presentation/deviceIdentity'
import { demoDeviceNameEntries } from '../../shared/presentation/deviceIdentity'

const demoDeviceNames = new Map(demoDeviceNameEntries())

function labelDeviceReferences(node: ReactNode, dataProfile: DataProfile): ReactNode {
  if (dataProfile !== 'demo') return node
  if (typeof node === 'string') {
    return node.split(/(DEMO-AGM-\d{3})/g).map((part, index) => {
      const displayName = demoDeviceNames.get(part)
      if (!displayName) return part
      const assetnum = part
      return <span className="assistant-device-reference" key={`${assetnum}-${index}`}><span>{displayName}</span><small>设备编号 {assetnum}</small></span>
    })
  }
  if (Array.isArray(node)) return node.map((child) => labelDeviceReferences(child, dataProfile))
  if (isValidElement(node)) {
    const element = node as ReactElement<{ children?: ReactNode; className?: string }>
    if (element.type === 'code' || element.props.className === 'assistant-device-reference') return node
    return cloneElement(element, undefined, labelDeviceReferences(element.props.children, dataProfile))
  }
  return node
}

export function AssistantMarkdown({ content, dataProfile }: { content: string; dataProfile: DataProfile }) {
  const components: Components = {
    table({ children }) {
      return <div className="assistant-markdown__table" role="region" aria-label="可横向滚动的表格" tabIndex={0}>
        <table>{children}</table>
      </div>
    },
    p({ children, ...props }) { return <p {...props}>{labelDeviceReferences(children, dataProfile)}</p> },
    li({ children, ...props }) { return <li {...props}>{labelDeviceReferences(children, dataProfile)}</li> },
    th({ children, ...props }) { return <th {...props}>{labelDeviceReferences(children, dataProfile)}</th> },
    td({ children, ...props }) { return <td {...props}>{labelDeviceReferences(children, dataProfile)}</td> },
    img({ alt }) { return <span>{labelDeviceReferences(alt, dataProfile)}</span> },
  }
  return <div className="assistant-markdown">
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>{content}</ReactMarkdown>
  </div>
}
