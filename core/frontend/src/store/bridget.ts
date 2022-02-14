import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { Bridge } from '@/types/bridges'

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

  @Mutation
  setUpdatingBridges(updating: boolean): void {
    this.updating_bridges = updating
  }

  @Mutation
  setUpdatingSerialPorts(updating: boolean): void {
    this.updating_serial_ports = updating
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
}

export { BridgetStore }

const bridget: BridgetStore = getModule(BridgetStore)
export default bridget
