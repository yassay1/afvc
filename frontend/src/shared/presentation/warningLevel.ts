const warningLevelTones = new Map([
  ['红色预警', 'warning-level--red'],
  ['橙色预警', 'warning-level--orange'],
  ['黄色预警', 'warning-level--yellow'],
  ['绿色关注', 'warning-level--green'],
])

export function warningLevelClass(level: string | null | undefined) {
  return warningLevelTones.get(level ?? '') ?? 'warning-level--neutral'
}
