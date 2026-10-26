import type { DataProfile } from '../presentation/deviceIdentity'
import { deviceDisplayName } from '../presentation/deviceIdentity'

type DeviceIdentityProps = {
  assetnum: string
  dataProfile: DataProfile
  realName?: string | null
  as?: 'span' | 'div' | 'h1' | 'h2'
  className?: string
}

export function DeviceIdentity({ assetnum, dataProfile, realName, as: Tag = 'span', className = '' }: DeviceIdentityProps) {
  return <Tag className={`device-identity${className ? ` ${className}` : ''}`}>
    <span className="device-identity__name">{deviceDisplayName(assetnum, dataProfile, realName)}</span>
    <small className="device-identity__number">设备编号 {assetnum}</small>
  </Tag>
}
