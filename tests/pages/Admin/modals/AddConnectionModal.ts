import { testId } from '$lib/utils/testId';
import type { Page } from '@playwright/test';
import { BaseModal } from '../../../components/BaseModal';

/**
 * Represents the Add(/Edit) Connection modal.
 *
 * Modal is opened by clicking the configure button on the {@link AdminSettingsConnectionsTab} for an API connection.
 *
 * See also `AddConnectionModal.svelte`.
 */
export class AddConnectionModal extends BaseModal {
	constructor(page: Page) {
		super(page, testId('AdminSettings', 'Connections', 'AddConnectionModal'));
	}

	private prefixInput = this.page.getByTestId(
		testId('AdminSettings', 'Connections', 'AddConnectionModal', 'PrefixIDInput')
	);
	private saveButton = this.page.getByTestId(
		testId('AdminSettings', 'Connections', 'AddConnectionModal', 'SaveButton')
	);

	async setPrefix(prefix: string): Promise<void> {
		await this.prefixInput.fill(prefix);
	}

	/** Saves the connection configuration and closes the modal.
	 *
	 * Saves the prefix configuration for the connection.
	 * The modal will close automatically after saving.
	 */
	async saveAndClose(): Promise<void> {
		await this.saveButton.click();
	}
}
