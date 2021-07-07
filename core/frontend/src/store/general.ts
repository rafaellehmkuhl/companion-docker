import { Module, VuexModule, Mutation } from 'vuex-module-decorators'
import { ErrorDialog } from '@/types/wifi'
import store from '@/store'

@Module({
  dynamic: true,
  store,
  name: 'general_store',
})

@Module
export default class GeneralStore extends VuexModule {
  error_dialogs: ErrorDialog[] = []
  show_error_dialog = false
  error_message = ''

  @Mutation
  openErrorDialog (error_dialog: ErrorDialog): void {
    this.error_dialogs.push(error_dialog)
  }
  
  @Mutation
  closeErrorDialog (error_dialog_index: string): void {
    this.error_dialogs = this.error_dialogs.filter(
      (error_dialog) => error_dialog.index != error_dialog_index,
    )
  }

  @Mutation
  setErrorDialog (state: boolean): void {
    this.show_error_dialog = state
  }

  @Mutation
  setErrorMessage (message: string): void {
    this.error_message = message
  }


  get errorDialogState (): boolean { return this.error_dialogs.length > 0 }
  get errorMessage (): string {
    return this.error_dialogs.length > 0 ? this.error_dialogs[this.error_dialogs.length - 1].message : ''
  }
}