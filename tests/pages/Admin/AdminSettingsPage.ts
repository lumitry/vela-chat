import type { Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';
import { AdminPage } from './AdminPage';

/**
 * Represents the Admin Settings - Settings page.
 *
 * URL base: /admin/settings (note: this will auto-append #general to the url and take you to AdminSettingsGeneralTab).
 */
export abstract class AdminSettingsPage extends AdminPage {
	constructor(page: Page) {
		super(page);
	}

	/**
	 * Helper method to get the tab button for a given tab name.
	 * @param tab the name of the tab to get the button for
	 * @returns the tab button for the given tab name
	 */
	private getTabButton(tab: string) {
		return this.page.getByTestId(testId('AdminSettings', 'TabButton', tab));
	}

	// TODO make the actual pageobjects for these tabs...
	/** Page Object: AdminSettingsGeneralTab */
	private generalTabButton = this.getTabButton('General');
	/** Page Object: AdminSettingsConnectionsTab */
	private connectionsTabButton = this.getTabButton('Connections');
	/** Page Object: AdminSettingsModelsTab */
	private modelsTabButton = this.getTabButton('Models');
	/** Page Object: AdminSettingsEvaluationsTab */
	private evaluationsTabButton = this.getTabButton('Evaluations');
	/** Page Object: AdminSettingsFunctionsTab */
	private functionsTabButton = this.getTabButton('Tools');
	/** Page Object: AdminSettingsDocumentsTab */
	private documentsTabButton = this.getTabButton('Documents');
	/** Page Object: AdminSettingsWebSearchTab */
	private webSearchTabButton = this.getTabButton('WebSearch');
	/** Page Object: AdminSettingsCodeExecutionTab */
	private codeExecutionTabButton = this.getTabButton('CodeExecution');
	/** Page Object: AdminSettingsInterfaceTab */
	private interfaceTabButton = this.getTabButton('Interface');
	/** Page Object: AdminSettingsAudioTab */
	private audioTabButton = this.getTabButton('Audio');
	/** Page Object: AdminSettingsImagesTab */
	private imagesTabButton = this.getTabButton('Images');
	/** Page Object: AdminSettingsPipelinesTab */
	private pipelinesTabButton = this.getTabButton('Pipelines');
	/** Page Object: AdminSettingsDatabaseTab */
	private databaseTabButton = this.getTabButton('Database');

	/**
	 * The save button at the bottom of the pages.
	 */
	private saveButton = this.page.getByTestId(testId('AdminSettings', 'Settings', 'SaveButton'));

	async clickGeneralTabButton(): Promise<void> {
		await this.generalTabButton.click();
	}

	async clickConnectionsTabButton(): Promise<void> {
		await this.connectionsTabButton.click();
	}

	async clickModelsTabButton(): Promise<void> {
		await this.modelsTabButton.click();
	}

	async clickEvaluationsTabButton(): Promise<void> {
		await this.evaluationsTabButton.click();
	}

	async clickFunctionsTabButton(): Promise<void> {
		await this.functionsTabButton.click();
	}

	async clickDocumentsTabButton(): Promise<void> {
		await this.documentsTabButton.click();
	}

	async clickWebSearchTabButton(): Promise<void> {
		await this.webSearchTabButton.click();
	}

	async clickCodeExecutionTabButton(): Promise<void> {
		await this.codeExecutionTabButton.click();
	}

	async clickInterfaceTabButton(): Promise<void> {
		await this.interfaceTabButton.click();
	}

	async clickAudioTabButton(): Promise<void> {
		await this.audioTabButton.click();
	}

	async clickImagesTabButton(): Promise<void> {
		await this.imagesTabButton.click();
	}

	async clickPipelinesTabButton(): Promise<void> {
		await this.pipelinesTabButton.click();
	}

	async clickDatabaseTabButton(): Promise<void> {
		await this.databaseTabButton.click();
	}

	async clickSaveButton(): Promise<void> {
		await this.saveButton.click();
	}
}
