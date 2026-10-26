export function StateMessage({ title, detail, retry }: { title: string; detail: string; retry?: () => void }) {
  return (
    <div className="state-message" role="status">
      <strong>{title}</strong>
      <p>{detail}</p>
      {retry && <button type="button" onClick={retry}>重试</button>}
    </div>
  )
}
