import axios from 'axios'
import { Module, VuexModule, Mutation, Action, getModule } from 'vuex-module-decorators'
import { Network, NetworkCredentials, WPAState, WPANetwork, SavedNetwork, WifiStatus } from '@/types/wifi'
import GeneralStore from './general'
import store from '@/store'

const API_URL = 'wifi-manager/v1.0'

const general = getModule(GeneralStore)

@Module({
  dynamic: true,
  store,
  name: 'wifi_store',
})
export default class WifiStore extends VuexModule {
  current_wifi_ip: string | null = null
  current_wifi_network: Network | null = null
  wpa_state: WPAState | null = null
  wifi_network_status: WifiStatus | null = null
  available_wifi_networks: Network[] = []
  saved_wifi_networks: Network[] = []

  @Mutation
  setCurrentWifiNetwork (network: Network | null): void {
    this.current_wifi_network = network
  }

  @Mutation
  setAvailableWifiNetworks (available_wifi_networks: Network[]): void {
    this.available_wifi_networks = available_wifi_networks
  }

  @Mutation
  changeWifiNetworkStatus (status: WifiStatus | null): void {
    this.wifi_network_status = status
  }

  @Mutation
  changeWPAState (state: WPAState): void {
    this.wpa_state = state
  }

  @Action
  connectToWifiNetwork (network_info: {credentials: NetworkCredentials, hidden: boolean}): Promise<void> {
    console.log(`${network_info.credentials.ssid} / ${network_info.credentials.password} / ${network_info.hidden}`)
    return axios({
      method: 'post',
      url: `${API_URL}/connect`,
      timeout: 500,
      data: network_info.credentials,
      params: { hidden: network_info.hidden },
    })
      .then(() => (
        this.changeWPAState('UNDEFINED'),
        this.changeWifiNetworkStatus(null),
        general.closeErrorDialog('connect_fail')
      ))
      .catch(() => general.openErrorDialog({
        index: 'connect_fail',
        message: 'Could not connect to wifi network.',
      }))
  }

  @Action
  removeSavedWifiNetwork (ssid: string): Promise<void> {
    return axios({
      method: 'post',
      url: `${API_URL}/remove`,
      timeout: 500,
      params: {ssid},
    })
      .then(() => general.closeErrorDialog('saved_remove_fail'))
      .catch(() => general.openErrorDialog({
        index: 'saved_remove_fail',
        message: 'Could not remove saved wifi network.',
      }))
  }

  @Action
  disconnectFromWifiNetwork (): Promise<void> {
    return axios({
      method: 'get',
      url: `${API_URL}/disconnect`,
      timeout: 500,
    })
      .then(() => (
        this.changeWPAState('UNDEFINED'),
        this.changeWifiNetworkStatus(null),
        this.setCurrentWifiNetwork(null),
        general.closeErrorDialog('disconnect_fail')
      ))
      .catch(() => general.openErrorDialog({
        index: 'disconnect_fail',
        message: 'Could not disconnect from wifi network.',
      }))
  }

  @Action
  async updateWifiNetworkStatus (): Promise<void> {
    return await axios({
      method: 'get',
      url: `${API_URL}/status`,
      timeout: 1000,
    })
      .then((response) => {
        this.changeWPAState(response.data.wpa_state)
        this.changeWifiNetworkStatus(response.data)

        if (response.data.wpa_state != 'COMPLETED') {
          this.setCurrentWifiNetwork(null)
          return
        }

        let signal = 0
        let locked = false
    
        const network_on_available = this.available_wifi_networks.filter(
          (network) => network.ssid === response.data.ssid,
        )[0]
        if (network_on_available) {
          signal = network_on_available.signal
          locked = network_on_available.locked
        }

        this.setCurrentWifiNetwork({
          ssid: response.data.ssid,
          signal,
          locked,
          saved: true,
        })
        general.closeErrorDialog('status_fail')
      })
      .catch(() => (
        general.openErrorDialog({index: 'status_fail', message: 'Could not fetch wifi network status.'}),
        this.setCurrentWifiNetwork(null)
      ))
  }

  @Action
  async scanAvailableWifiNetworks (): Promise<void> {
    const available_response = await axios.get(`${API_URL}/scan`, {timeout: 15000})
    if (available_response.status != 200) {
      general.openErrorDialog({index: 'scan_fail', message: 'Could not scan wifi networks.'})
      return
    }
    general.closeErrorDialog('scan_fail')

    const saved_response = await axios.get(`${API_URL}/saved`, {timeout: 1000})
    if (saved_response.status != 200) {
      general.openErrorDialog({index: 'get_saved_fail', message: 'Could not get saved wifi networks.'})
      return
    }
    general.closeErrorDialog('get_saved_fail')

    const saved_networks_json = await saved_response.data
    const saved_networks_ssids = saved_networks_json.map((network: SavedNetwork) => network['ssid'])

    const available_networks_json = await available_response.data
    const available_wifi_networks = available_networks_json.map((network: WPANetwork) => {
      return {
        ssid: network.ssid,
        signal: network.signallevel,
        locked: network.flags.includes('WPA'),
        saved: saved_networks_ssids.includes(network.ssid),
      }
    })

    this.setAvailableWifiNetworks(available_wifi_networks)
  }

}