const demoDeviceNames: Record<string, string> = {
  'DEMO-AGM-001': '星澜站闸机 01', 'DEMO-AGM-002': '星澜站闸机 02', 'DEMO-AGM-003': '星澜站闸机 03',
  'DEMO-AGM-004': '云桥站闸机 01', 'DEMO-AGM-005': '云桥站闸机 02', 'DEMO-AGM-006': '云桥站闸机 03',
  'DEMO-AGM-007': '青禾站闸机 01', 'DEMO-AGM-008': '青禾站闸机 02', 'DEMO-AGM-009': '青禾站闸机 03',
  'DEMO-AGM-010': '北辰站闸机 01', 'DEMO-AGM-011': '北辰站闸机 02', 'DEMO-AGM-012': '北辰站闸机 03',
  'DEMO-AGM-013': '松影站闸机 01', 'DEMO-AGM-014': '松影站闸机 02', 'DEMO-AGM-015': '松影站闸机 03',
  'DEMO-AGM-016': '月港站闸机 01', 'DEMO-AGM-017': '月港站闸机 02', 'DEMO-AGM-018': '月港站闸机 03',
  'DEMO-AGM-019': '晴川站闸机 01', 'DEMO-AGM-020': '晴川站闸机 02', 'DEMO-AGM-021': '晴川站闸机 03',
  'DEMO-AGM-022': '锦湖站闸机 01', 'DEMO-AGM-023': '锦湖站闸机 02', 'DEMO-AGM-024': '锦湖站闸机 03',
  'DEMO-AGM-025': '梧桐站闸机 01', 'DEMO-AGM-026': '梧桐站闸机 02', 'DEMO-AGM-027': '梧桐站闸机 03',
  'DEMO-AGM-028': '晨光站闸机 01', 'DEMO-AGM-029': '晨光站闸机 02', 'DEMO-AGM-030': '晨光站闸机 03',
  'DEMO-AGM-031': '远帆站闸机 01', 'DEMO-AGM-032': '远帆站闸机 02', 'DEMO-AGM-033': '远帆站闸机 03',
  'DEMO-AGM-034': '银湾站闸机 01', 'DEMO-AGM-035': '银湾站闸机 02', 'DEMO-AGM-036': '银湾站闸机 03',
}

export type DataProfile = 'demo' | 'production' | undefined

export function deviceDisplayName(assetnum: string, profile: DataProfile, realName?: string | null) {
  if (profile === 'demo') return demoDeviceNames[assetnum] || assetnum
  return realName?.trim() || assetnum
}

export function demoDeviceNameEntries() {
  return Object.entries(demoDeviceNames)
}

