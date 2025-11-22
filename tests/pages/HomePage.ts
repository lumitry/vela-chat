import { expect, type Page } from '@playwright/test';
import { BasePage } from './BasePage';

export class HomePage extends BasePage {
	constructor(page: Page) {
		super(page);
	}
}
