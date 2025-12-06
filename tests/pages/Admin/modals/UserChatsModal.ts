import { testId } from '$lib/utils/testId';
import type { Page } from '@playwright/test';
import { BaseModal } from '../../../components/BaseModal';

/**
 * Represents the User Chats modal.
 *
 * Modal is opened by clicking one of the chats buttons on the {@link AdminUsersPage}.
 */
export class UserChatsModal extends BaseModal {
	/** Title of the chat. Clicking this opens the chat in a new tab! */
	private getChatTitle = (index: number) =>
		this.page.getByTestId(
			testId('AdminSettings', 'Users', 'UserChatsModal', 'ChatTitle', `${index}`)
		);
	private getChatUpdatedAt = (index: number) =>
		this.page.getByTestId(
			testId('AdminSettings', 'Users', 'UserChatsModal', 'ChatUpdatedAt', `${index}`)
		);
	private getDeleteChatButton = (index: number) =>
		this.page.getByTestId(
			testId('AdminSettings', 'Users', 'UserChatsModal', 'DeleteChatButton', `${index}`)
		);

	private chatRows = this.page.getByTestId(
		testId('AdminSettings', 'Users', 'UserChatsModal', 'ChatRow')
	);

	constructor(page: Page) {
		super(page, testId('AdminSettings', 'Users', 'UserChatsModal'));
	}

	/** Waits for the rows of the chats modal to be visible. */
	async waitForVisible(): Promise<void> {
		await this.chatRows.first().waitFor({ state: 'visible', timeout: 10000 });
	}

	/** Clicks the title of a chat to open it in a new tab. */
	async clickChatTitle(index: number): Promise<void> {
		await this.getChatTitle(index).click();
	}

	/** Clicks the delete button of a chat to delete it. */
	async clickDeleteChatButton(index: number): Promise<void> {
		await this.getDeleteChatButton(index).click();
	}

	async getNumberOfChats(): Promise<number> {
		return await this.chatRows.count();
	}

	async getChatTitleText(index: number): Promise<string> {
		return (await this.getChatTitle(index).textContent()) ?? '';
	}

	async getChatUpdatedAtText(index: number): Promise<string> {
		return (await this.getChatUpdatedAt(index).textContent()) ?? '';
	}
}
