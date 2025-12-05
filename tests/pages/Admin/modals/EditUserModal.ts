import { testId } from '$lib/utils/testId';
import type { Page } from '@playwright/test';
import { BaseModal } from '../../../components/BaseModal';

export type EditUserModaEditableField = 'name' | 'email' | 'password';

/**
 * Represents the Edit User modal.
 *
 * Modal is opened by clicking one of the edit user buttons on the {@link AdminUsersPage}.
 */
export class EditUserModal extends BaseModal {
	constructor(page: Page) {
		super(page, testId('AdminSettings', 'Users', 'EditUserModal'));
	}

	private userImage = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'UserImage')
	);
	private userName = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'Name')
	);
	private userCreatedAt = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'CreatedAt')
	);
	private nameInput = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'NameInput')
	);
	private emailInput = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'EmailInput')
	);
	private passwordInput = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'PasswordInput')
	);
	private saveButton = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'EditUserModal', 'SaveButton')
	);

	/** Saves the user and closes the modal.
	 *
	 * The modal will close automatically after saving.
	 */
	async saveAndClose(): Promise<void> {
		await this.saveButton.click();
	}

	async setName(name: string): Promise<void> {
		await this.nameInput.fill(name);
	}

	async setEmail(email: string): Promise<void> {
		await this.emailInput.fill(email);
	}

	async setPassword(password: string): Promise<void> {
		await this.passwordInput.fill(password);
	}

	/** Gets the username according to the user name display, NOT the input's value! */
	async getUserName(): Promise<string> {
		return (await this.userName.textContent()) ?? '';
	}

	async getUserCreatedAt(): Promise<number> {
		const value = await this.userCreatedAt.getAttribute('data-value');
		return value ? parseInt(value) : 0;
	}

	async getUserImageUrl(): Promise<string> {
		return (await this.userImage.getAttribute('src')) ?? '';
	}

	/** Sets a field of the user. */
	async setField(field: EditUserModaEditableField, value: string): Promise<void> {
		switch (field) {
			case 'name':
				await this.setName(value);
				break;
			case 'email':
				await this.setEmail(value);
				break;
			case 'password':
				await this.setPassword(value);
				break;
			default:
				throw new Error(`Invalid field: ${field}`);
		}
	}

	/** Sets multiple fields of the user. */
	async setFields(fields: Record<EditUserModaEditableField, string>): Promise<void> {
		for (const [field, value] of Object.entries(fields)) {
			await this.setField(field as EditUserModaEditableField, value);
		}
	}
}
