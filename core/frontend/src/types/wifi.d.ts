export interface Network {
    ssid: string
    signal: number
    locked: boolean
    saved: boolean
}

export interface WifiStatus {
    bssid: string
    freq: int
    ssid: string
    id: int
    mode: string
    wifi_generation: int
    pairwise_cipher: string
    group_cipher: string
    key_mgmt: string
    wpa_state: string
    ip_address: string
    p2p_device_address: string
    address: string
    uuid: string
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

export type WPAState = 'UNDEFINED' | 'DISCONNECTED' | 'INTERFACE_DISABLED'
    | 'INACTIVE' | 'SCANNING' | 'AUTHENTICATING' | 'ASSOCIATING' | 'ASSOCIATED'
    | '4WAY_HANDSHAKE' | 'GROUP_HANDSHAKE' | 'COMPLETED' 
