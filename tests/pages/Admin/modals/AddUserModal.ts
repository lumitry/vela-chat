import { testId } from '$lib/utils/testId';
import type { Page } from '@playwright/test';
import { BaseModal } from '../../../components/BaseModal';

/**
 * Represents the Add User modal.
 *
 * Modal is opened by clicking the add user button on the {@link AdminUsersPage}.
 *
 * Opened from URL `/admin/users` then clicking the `+` button.
 *
 * See also `AddUserModal.svelte`.
 *
 * By default, the modal is opened on the form tab.
 */
export class AddUserModal extends BaseModal {
	constructor(page: Page) {
		super(page, testId('AdminSettings', 'Users', 'AddUserModal'));
	}

	private formTabButton = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'AddUserModal', 'FormTabButton')
	);
	private csvImportTabButton = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'AddUserModal', 'CSVImportTabButton')
	);
	private saveButton = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'AddUserModal', 'SaveButton')
	);
	private uploadCSVInput = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'AddUserModal', 'UploadCSVInput')
	);

	async clickFormTabButton(): Promise<void> {
		await this.formTabButton.click();
	}

	async clickCSVImportTabButton(): Promise<void> {
		await this.csvImportTabButton.click();
	}

	async clickSaveButton(): Promise<void> {
		await this.saveButton.click();
	}

	/**
	 * Uploads a CSV file to the CSV import tab.
	 * @param file - A file object where the file content is in the `buffer` property.
	 * @example
	 * ```typescript
	 * await addUserModal.uploadCSVFile({
	 *     name: 'users.csv',
	 *     mimeType: 'text/csv',
	 *     buffer: Buffer.from(generateUsersCSV())
	 * });
	 * ```
	 */
	async uploadCSVFile(file: { name: string; mimeType: string; buffer: Buffer }): Promise<void> {
		await this.uploadCSVInput.setInputFiles([
			{
				name: file.name,
				buffer: file.buffer,
				mimeType: file.mimeType
			}
		]);
	}
}
