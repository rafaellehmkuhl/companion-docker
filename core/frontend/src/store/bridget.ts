import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import notifications from '@/store/notifications'
import { Bridge } from '@/types/bridges'
import { bridget_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

@Module({
  dynamic: true,
  store,
  name: 'bridget',
})

class BridgetStore extends VuexModule {
  API_URL = '/bridget/v1.0'

  available_bridges: Bridge[] = []

  available_serial_ports: string[] = []

  should_fetch = false

  updating_bridges = true

  updating_serial_ports = true

  prefetched_bridges = false

  prefeteched_serial_ports = false

  @Mutation
  setUpdatingBridges(updating: boolean): void {
    this.updating_bridges = updating
  }

  @Mutation
  setUpdatingSerialPorts(updating: boolean): void {
    this.updating_serial_ports = updating
  }

  @Mutation
  setPrefetchedBridges(prefetched: boolean): void {
    this.prefetched_bridges = prefetched
  }

  @Mutation
  setPrefetchedSerialPorts(prefetched: boolean): void {
    this.prefeteched_serial_ports = prefetched
  }

  @Mutation
  setAvailableBridges(available_bridges: Bridge[]): void {
    this.available_bridges = available_bridges
    this.updating_bridges = false
  }

  @Mutation
  setAvailableSerialPorts(available_serial_ports: string[]): void {
    this.available_serial_ports = available_serial_ports
    this.updating_bridges = false
  }

  @Mutation
  startFetching(): void {
    this.should_fetch = true
  }

  @Mutation
  stopFetching(): void {
    this.should_fetch = false
  }

  @Action
  async fetchAvailableBridges(): Promise<void> {
    if (this.prefetched_bridges && !this.should_fetch) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/bridges`,
      timeout: 10000,
    })
      .then((response) => {
        const available_bridges = response.data
        this.setAvailableBridges(available_bridges)
        this.setPrefetchedBridges(true)
      })
      .catch((error) => {
        this.setAvailableBridges([])
        if (error === backend_offline_error) { return }
        const message = `Could not fetch available bridges: ${error.message}`
        notifications.pushError({ service: bridget_service, type: 'BRIDGES_FETCH_FAIL', message })
      })
      .finally(() => {
        this.setUpdatingBridges(false)
      })
  }

  @Action
  async fetchAvailableSerialPorts(): Promise<void> {
    if (this.prefeteched_serial_ports && !this.should_fetch) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/serial_ports`,
      timeout: 10000,
    })
      .then((response) => {
        const available_ports = response.data
        this.setAvailableSerialPorts(available_ports)
        this.setPrefetchedSerialPorts(true)
      })
      .catch((error) => {
        this.setAvailableSerialPorts([])
        if (error === backend_offline_error) { return }
        const message = `Could not fetch available serial ports: ${error.message}`
        notifications.pushError({ service: bridget_service, type: 'BRIDGET_SERIAL_PORTS_FETCH_FAIL', message })
      })
      .finally(() => {
        this.setUpdatingSerialPorts(false)
      })
  }
}

export { BridgetStore }

const bridget: BridgetStore = getModule(BridgetStore)
callPeriodically(bridget.fetchAvailableBridges, 5000)
callPeriodically(bridget.fetchAvailableSerialPorts, 5000)
export default bridget
