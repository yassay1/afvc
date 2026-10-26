import { Image } from 'lucide-react'
import { useDataProfile } from '../query/dataProfile'
import { demoImageForDevice } from '../presentation/demoDeviceImage'

export function DeviceImage({ assetnum, className = '' }: { assetnum: string; className?: string }) {
  const profile = useDataProfile()
  const classNames = `device-photo${className ? ` ${className}` : ''}`
  if (profile.data?.data_profile !== 'demo') {
    return <span className={`${classNames} device-photo--empty`} aria-hidden="true"><Image size={22} strokeWidth={1.6} /></span>
  }
  return <span className={classNames}><img src={demoImageForDevice(assetnum)} alt="" loading="lazy" /></span>
}
