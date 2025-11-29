import { expect, type Page } from '@playwright/test';
import { testId } from '$lib/utils/testId';

/**
 * Represents the Command Palette component.
 *
 * The command palette is always in the DOM (rendered off-screen for instant opening),
 * so we check `aria-hidden` attribute instead of `isVisible()` to determine if it's open.
 *
 * @example
 * ```typescript
 * const basePage = new BasePage(page);
 * await basePage.commandPalette.open('cmd+p');
 * await basePage.commandPalette.typeCommand('settings');
 * await basePage.commandPalette.clickCommand('settings:open');
 * ```
 */
export class CommandPalette {
	private commandPalette: ReturnType<Page['getByTestId']>;
	private getCommandPaletteCommandInput: ReturnType<Page['getByTestId']>;
	private getCommandPaletteCommandButton: (commandId: string) => ReturnType<Page['getByTestId']>;
	private getCommandPaletteSubmenuItemButton: (
		submenuItemId: string
	) => ReturnType<Page['getByTestId']>;

	constructor(private page: Page) {
		this.commandPalette = this.page.getByTestId(testId('CommandPalette'));
		this.getCommandPaletteCommandInput = this.page.getByTestId(
			testId('CommandPalette', 'CommandInput')
		);
		this.getCommandPaletteCommandButton = (commandId: string) =>
			this.page.getByTestId(testId('CommandPalette', 'CommandItem', commandId));
		this.getCommandPaletteSubmenuItemButton = (submenuItemId: string) =>
			this.page.getByTestId(testId('CommandPalette', 'SubmenuItem', submenuItemId));
	}

	/**
	 * Open the command palette.
	 * @param shortcut - The shortcut to use to open the command palette. Defaults to 'cmd+p'.
	 */
	async open(shortcut: 'cmd+p' | 'cmd+k' | 'cmd+e' | 'double-shift' = 'cmd+p'): Promise<void> {
		if (shortcut === 'double-shift') {
			// Double-shift requires two Shift presses within 400ms
			// Press Shift twice quickly
			await this.page.keyboard.press('Shift');
			await this.page.waitForTimeout(50); // Small delay between presses
			await this.page.keyboard.press('Shift');
		} else {
			const shortcutReplaced = shortcut.replace('cmd', 'ControlOrMeta');
			await this.page.keyboard.press(`${shortcutReplaced}`);
		}
		// Wait for the command palette to be open (aria-hidden="false")
		await expect(this.commandPalette).toHaveAttribute('aria-hidden', 'false', { timeout: 2000 });
	}

	/**
	 * Types a text into the command palette input. Does NOT submit the command.
	 *
	 * Can also be used in submenus.
	 *
	 * @param searchText - The text to type into the command palette input.
	 */
	async typeCommand(searchText: string): Promise<void> {
		await this.getCommandPaletteCommandInput.fill(searchText);
	}

	/**
	 * Submits the command palette input.
	 */
	async submitCommand(): Promise<void> {
		await this.getCommandPaletteCommandInput.press('Enter');
	}

	/**
	 * Clicks a command in the command palette.
	 *
	 * @param commandId - The ID of the command to click.
	 */
	async clickCommand(commandId: string): Promise<void> {
		await this.getCommandPaletteCommandButton(commandId).click();
	}

	/**
	 * Clicks a submenu item in the command palette.
	 *
	 * @param submenuItemId - The ID of the submenu item to click.
	 */
	async clickSubmenuItem(submenuItemId: string): Promise<void> {
		await this.getCommandPaletteSubmenuItemButton(submenuItemId).click();
	}

	/**
	 * Assert that a submenu item exists in the command palette.
	 *
	 * @param submenuItemId - The ID of the submenu item to check.
	 */
	async assertSubmenuItemExists(submenuItemId: string): Promise<void> {
		await expect(this.getCommandPaletteSubmenuItemButton(submenuItemId)).toBeVisible();
	}

	/**
	 * Assert that a submenu item contains the expected text.
	 *
	 * @param submenuItemId - The ID of the submenu item to check.
	 * @param text - The expected text.
	 */
	async assertSubmenuItemContainsText(submenuItemId: string, text: string): Promise<void> {
		await expect(this.getCommandPaletteSubmenuItemButton(submenuItemId)).toContainText(text);
	}

	/**
	 * Closes the command palette by clicking the backdrop or pressing Escape, and waits for it to actually close.
	 *
	 * Similar to BaseModal.close(), this tries clicking the backdrop first (which is more reliable),
	 * then falls back to Escape if needed. Handles cases where a submenu is open.
	 * Waits for the command palette to be hidden before returning.
	 *
	 * Note: The command palette is always in the DOM (rendered off-screen for instant opening),
	 * so we check `aria-hidden` attribute instead of `isVisible()` to determine if it's closed.
	 */
	async close(): Promise<void> {
		// Check if command palette is open by checking aria-hidden attribute
		// When closed, aria-hidden="true"; when open, aria-hidden="false"
		const ariaHidden = await this.commandPalette.getAttribute('aria-hidden');
		if (ariaHidden === 'true') {
			// Already closed, nothing to do
			return;
		}

		// Check if there's a submenu open - if so, close it first with Escape
		const submenuLocator = this.page
			.locator('[data-testid^="CommandPalette_SubmenuItem_"]')
			.first();
		const hasSubmenu = await submenuLocator.isVisible().catch(() => false);

		if (hasSubmenu) {
			// Close submenu first
			await this.page.keyboard.press('Escape');
			// Wait for submenu to disappear
			await submenuLocator.waitFor({ state: 'hidden', timeout: 1000 }).catch(() => {
				// Submenu might already be closed or not exist, continue anyway
			});
		}

		// Now close the main palette - try clicking backdrop first (like BaseModal does)
		// Click at the edge of the backdrop, not on the content
		// The backdrop has on:mousedown handler that closes the palette
		try {
			await this.commandPalette.click({ position: { x: 10, y: 10 } });
			// Wait a bit to see if it closed (check aria-hidden)
			await this.page
				.waitForFunction(
					(testId) => {
						const element = document.querySelector(`[data-testid="${testId}"]`);
						return element?.getAttribute('aria-hidden') === 'true';
					},
					testId('CommandPalette'),
					{ timeout: 500 }
				)
				.catch(() => {
					// If clicking didn't work, continue to Escape fallback
				});
		} catch {
			// If clicking failed, continue to Escape fallback
		}

		// Check if still open - if so, try Escape
		const stillOpen = (await this.commandPalette.getAttribute('aria-hidden')) !== 'true';
		if (stillOpen) {
			// Press Escape to close the command palette
			await this.page.keyboard.press('Escape');
		}

		// Wait for the command palette to actually be closed
		// Check aria-hidden="true" instead of isVisible() since the element is always in DOM
		await expect(this.commandPalette).toHaveAttribute('aria-hidden', 'true', { timeout: 2000 });
	}

	/**
	 * Assert that the command palette is open (aria-hidden="false").
	 */
	async assertIsOpen(): Promise<void> {
		await expect(this.commandPalette).toHaveAttribute('aria-hidden', 'false');
	}

	/**
	 * Assert that the command palette is closed (aria-hidden="true").
	 */
	async assertIsClosed(): Promise<void> {
		await expect(this.commandPalette).toHaveAttribute('aria-hidden', 'true');
	}
}
