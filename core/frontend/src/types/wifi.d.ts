export interface Network {
    ssid: string
    signal: number
    locked: boolean
    saved: boolean
}

export interface WPANetwork {
    ssid: string
    bssid: string
    flags: string
    frequency: number
    signallevel: number
}

export interface SavedNetwork {
    networkid: number
    ssid: string
    bssid: string
    flags: string
}

export class ErrorDialog {
    index: string
    message: string
}

export class NetworkCredentials {
    ssid: string
    password: string
}

export type NetworkStatus = 'UNDEFINED' | 'DISCONNECTED' | 'INTERFACE_DISABLED'
    | 'INACTIVE' | 'SCANNING' | 'AUTHENTICATING' | 'ASSOCIATING' | 'ASSOCIATED'
    | '4WAY_HANDSHAKE' | 'GROUP_HANDSHAKE' | 'COMPLETED' 
