import type { Locator, Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminSettingsPage } from './AdminSettingsPage';
import type { OllamaEndpoint, OpenAIEndpoint } from '../../data/endpoints';
import { AddConnectionModal } from './modals/AddConnectionModal';

/**
 * Represents the Admin Settings - Settings - Connections page.
 *
 * This is the page when navigating to /admin/settings#connections.
 *
 * URL: /admin/settings#connections
 */
export class AdminSettingsConnectionsTab extends AdminSettingsPage {
	// helper functions to get test id and locator for the current page
	private getPageTestId = (...args: string[]): string => {
		return testId('AdminSettings', 'Connections', ...args);
	};
	private getPageLocator = (...args: string[]): Locator => {
		return this.page.getByTestId(this.getPageTestId(...args));
	};

	//---------------//
	// Page Elements //
	//---------------//

	/*
	 * OpenAI connection elements
	 */
	/** Enables/disables all OpenAI API connections */
	private enableOpenAISwitch = this.getPageLocator('EnableOpenAISwitch');
	/** the plus button to add a new OpenAI-compatible endpoint */
	private addOpenAIConnectionButton = this.getPageLocator('AddOpenAIConnectionButton');

	// the below fields are repeated for each OpenAI API connection,   //
	// so be sure to use the correct index when interacting with them! //

	/** the input field for each OpenAI base URL */
	private openAIBaseURLInput = this.getPageLocator('OpenAIConnectionBaseURLInput');
	/** the input field for each OpenAI API key */
	private openAIAPIKeyInput = this.getPageLocator('OpenAIConnectionAPIKeyInput');
	/** the visibility toggle for each OpenAI API connection */
	private openAIVisibilityToggleButton = this.getPageLocator('OpenAIVisibilityToggleButton');
	/** the configure button for each OpenAI API connection (opens the EditConnectionModal) */
	private openAIAPIConfigureButton = this.getPageLocator('OpenAIConnectionAPIConfigureButton');

	/*
	 * Ollama connection elements
	 */

	/** Enables/disables all Ollama API connections */
	private enableOllamaSwitch = this.getPageLocator('EnableOllamaSwitch');
	/** the plus button to add a new Ollama endpoint */
	private addOllamaConnectionButton = this.getPageLocator('AddOllamaConnectionButton');

	// the below fields are repeated for each Ollama endpoint,         //
	// so be sure to use the correct index when interacting with them! //

	/** the input field for each Ollama base URL */
	private ollamaBaseURLInput = this.getPageLocator('OllamaConnectionBaseURLInput');
	/** the input field for each Ollama API key */
	private ollamaAPIKeyInput = this.getPageLocator('OllamaAPIKeyInput');
	/** the visibility toggle for each Ollama API connection */
	private ollamaVisibilityToggleButton = this.getPageLocator('OllamaVisibilityToggleButton');
	/** the manage button for each Ollama API connection (opens the ManageOllamaModal) */
	private ollamaAPIManageButton = this.getPageLocator('OllamaConnectionManageButton');
	/** the configure button for each Ollama API connection (opens the EditConnectionModal) */
	private ollamaAPIConfigureButton = this.getPageLocator('OllamaConnectionConfigureButton');

	/*
	 * Other elements
	 */
	/** Enables/disables direct connections to user-provided OpenAI-compatible API endpoints. */
	private enableDirectConnectionsSwitch = this.getPageLocator('EnableDirectConnectionsSwitch');

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Sets the OpenAI API connection.
	 *
	 * @param endpoint The OpenAI API connection endpoint.
	 * @param index The index of the OpenAI API connection. If not provided, the first connection will be used.
	 */
	async setOpenAIConnection(endpoint: OpenAIEndpoint, index?: number): Promise<void> {
		// TODO handling if index is provided but that index doesn't exist yet (i.e. create the connection)
		if (index !== undefined) {
			await this.openAIBaseURLInput.nth(index).fill(endpoint.url);
			await this.openAIAPIKeyInput.nth(index).fill(endpoint.apiKey);
		} else {
			await this.openAIBaseURLInput.fill(endpoint.url);
			await this.openAIAPIKeyInput.fill(endpoint.apiKey);
		}
		if (endpoint.prefix) {
			await this.openAIAPIConfigureButton.nth(index ?? 0).click();
			const modal = new AddConnectionModal(this.page);
			await modal.setPrefix(endpoint.prefix);
			await modal.saveAndClose();
			await modal.waitForHidden();
		}
	}

	/**
	 * Sets the Ollama API connection.
	 *
	 * @param endpoint The Ollama API connection endpoint.
	 * @param index The index of the Ollama API connection. If not provided, the first connection will be used.
	 */
	async setOllamaConnection(endpoint: OllamaEndpoint, index?: number): Promise<void> {
		// TODO handling if index is provided but that index doesn't exist yet (i.e. create the connection)
		if (index !== undefined) {
			await this.ollamaBaseURLInput.nth(index).fill(endpoint.url);
		} else {
			await this.ollamaBaseURLInput.fill(endpoint.url);
		}
		if (endpoint.prefix) {
			await this.ollamaAPIConfigureButton.nth(index ?? 0).click();
			const modal = new AddConnectionModal(this.page);
			await modal.setPrefix(endpoint.prefix);
			await modal.saveAndClose();
			await modal.waitForHidden();
		}
	}

	/**
	 * Sets whether to enable all OpenAI API connections.
	 *
	 * @param enabled Whether to enable all OpenAI API connections.
	 */
	async setEnableOpenAISwitch(enabled: boolean): Promise<void> {
		await this.enableOpenAISwitch.setChecked(enabled);
	}

	/**
	 * Sets whether to enable all Ollama API connections.
	 *
	 * @param enabled Whether to enable all Ollama API connections.
	 */
	async setEnableOllamaSwitch(enabled: boolean): Promise<void> {
		await this.enableOllamaSwitch.setChecked(enabled);
	}

	/**
	 * Sets whether to enable direct connections to user-provided OpenAI-compatible API endpoints.
	 *
	 * @param enabled Whether to enable direct connections to user-provided OpenAI-compatible API endpoints.
	 */
	async setEnableDirectConnectionsSwitch(enabled: boolean): Promise<void> {
		await this.enableDirectConnectionsSwitch.setChecked(enabled);
	}

	// TODO: add more methods?
}
