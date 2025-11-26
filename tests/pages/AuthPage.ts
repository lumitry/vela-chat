import { expect, type Page } from '@playwright/test';
import { BasePage } from './BasePage';
import type { TestUser } from '../data/users';
import { testId } from '$lib/utils/testId';

/**
 * Authentication page modes.
 * Using a const object instead of enum for better tree-shaking and type inference.
 */
export const AuthMode = {
	SignIn: 'signin',
	SignUp: 'signup'
} as const;

/**
 * Type representing the authentication page mode.
 */
export type AuthMode = (typeof AuthMode)[keyof typeof AuthMode];

/**
 * Unified page object for the authentication page (auth/+page.svelte).
 * This page handles both sign-in and sign-up flows.
 */
export class AuthPage extends BasePage {
	// Common elements (available in both sign-in and sign-up modes)
	private emailInput = this.page.getByTestId(testId('AuthPage', 'EmailInput'));
	private passwordInput = this.page.getByTestId(testId('AuthPage', 'PasswordInput'));
	private submitButton = this.page.getByTestId(testId('AuthPage', 'SubmitButton'));
	/** Switches between sign-in and sign-up modes (may not be visible if signup is disabled) */
	private switchModeButton = this.page.getByTestId(testId('AuthPage', 'SwitchModeButton'));

	// Sign-up only element
	private nameInput = this.page.getByTestId(testId('AuthPage', 'NameInput'));

	constructor(page: Page) {
		super(page);
	}

	/**
	 * Sign in with the provided user credentials.
	 * Assumes the page is in sign-in mode.
	 */
	async signIn(user: TestUser): Promise<void> {
		await this.emailInput.fill(user.email);
		await this.passwordInput.fill(user.password);
		await this.submitButton.click();
	}

	/**
	 * Create a new account with the provided user credentials.
	 * Assumes the page is in sign-up mode.
	 */
	async signUp(user: TestUser): Promise<void> {
		await this.nameInput.fill(user.name);
		await this.emailInput.fill(user.email);
		await this.passwordInput.fill(user.password);
		await this.submitButton.click();
	}

	/**
	 * Switch the page mode between sign-in and sign-up.
	 * @throws If the switch mode button is not visible (e.g., when signup is disabled)
	 */
	async switchMode(): Promise<void> {
		await this.switchModeButton.click();
	}

	/**
	 * Get the current page mode.
	 * @returns The current page mode
	 */
	async getPageMode(): Promise<AuthMode> {
		// Wait for the form to be visible before checking mode
		await this.emailInput.waitFor({ state: 'visible' });
		return (await this.nameInput.isVisible()) ? AuthMode.SignUp : AuthMode.SignIn;
	}

	/**
	 * Assert that the current page mode is the expected mode.
	 * @param mode The expected mode
	 */
	async assertPageMode(mode: AuthMode): Promise<void> {
		const currentMode = await this.getPageMode();
		expect(currentMode).toBe(mode);
	}

	/**
	 * Switch the page mode between sign-in and sign-up if the current mode is not the intended mode.
	 * Otherwise, do nothing.
	 * @param intendedMode The intended mode
	 */
	async switchPageModeIfNeeded(intendedMode: AuthMode): Promise<void> {
		const currentMode = await this.getPageMode();
		if (currentMode !== intendedMode) {
			await this.switchMode();
		}
	}

	// Assertion methods for sign-in mode
	async assertEmailInputIsVisible(): Promise<void> {
		await expect(this.emailInput).toBeVisible();
	}

	async assertPasswordInputIsVisible(): Promise<void> {
		await expect(this.passwordInput).toBeVisible();
	}

	async assertSubmitButtonIsVisible(): Promise<void> {
		await expect(this.submitButton).toBeVisible();
	}

	// Assertion methods for sign-up mode
	async assertNameInputIsVisible(): Promise<void> {
		await expect(this.nameInput).toBeVisible();
	}

	/**
	 * Assert that the switch mode button is visible.
	 * Note: This button may not be visible if signup is disabled or during onboarding.
	 */
	async assertSwitchModeButtonIsVisible(): Promise<void> {
		await expect(this.switchModeButton).toBeVisible();
	}

	/**
	 * Assert that all sign-in form elements are visible.
	 */
	async assertSignInFormIsVisible(): Promise<void> {
		await this.assertEmailInputIsVisible();
		await this.assertPasswordInputIsVisible();
		await this.assertSubmitButtonIsVisible();
	}

	/**
	 * Assert that all sign-up form elements are visible.
	 */
	async assertSignUpFormIsVisible(): Promise<void> {
		await this.assertNameInputIsVisible();
		await this.assertEmailInputIsVisible();
		await this.assertPasswordInputIsVisible();
		await this.assertSubmitButtonIsVisible();
	}

	/**
	 * Check if an input field is invalid according to HTML5 validation.
	 * This checks the browser's native validation state, which triggers the validation tooltip.
	 * @param inputLocator The locator for the input field to check
	 * @returns true if the field is invalid, false otherwise
	 */
	private async isInputInvalid(
		inputLocator: ReturnType<typeof this.page.getByTestId>
	): Promise<boolean> {
		return await inputLocator.evaluate((input: HTMLInputElement) => {
			return !input.validity.valid;
		});
	}

	/**
	 * Get the validation message for an input field.
	 * This is the message shown in the browser's native validation tooltip.
	 * @param inputLocator The locator for the input field to check
	 * @returns The validation message, or empty string if valid
	 */
	private async getInputValidationMessage(
		inputLocator: ReturnType<typeof this.page.getByTestId>
	): Promise<string> {
		return await inputLocator.evaluate((input: HTMLInputElement) => {
			return input.validationMessage || '';
		});
	}

	/**
	 * Ensure validation state has been checked on an input field.
	 * This calls checkValidity() to ensure the browser has evaluated the field's validity.
	 * @param inputLocator The locator for the input field to check
	 */
	private async ensureValidationChecked(
		inputLocator: ReturnType<typeof this.page.getByTestId>
	): Promise<void> {
		await inputLocator.evaluate((input: HTMLInputElement) => {
			// This ensures the browser has checked validity (validation is synchronous)
			input.checkValidity();
		});
	}

	/**
	 * Assert that the name input field is invalid.
	 * Note: This should be called after attempting to submit the form (e.g., after calling signUp).
	 * The form submission attempt triggers the browser's native validation.
	 */
	async assertNameInputIsInvalid(): Promise<void> {
		await this.ensureValidationChecked(this.nameInput);
		const isInvalid = await this.isInputInvalid(this.nameInput);
		expect(isInvalid).toBe(true);

		// Also verify there's a validation message
		const message = await this.getInputValidationMessage(this.nameInput);
		expect(message.length).toBeGreaterThan(0);
	}

	/**
	 * Assert that the email input field is invalid.
	 * Note: This should be called after attempting to submit the form (e.g., after calling {@link signUp}).
	 * The form submission attempt triggers the browser's native validation.
	 */
	async assertEmailInputIsInvalid(): Promise<void> {
		await this.ensureValidationChecked(this.emailInput);
		const isInvalid = await this.isInputInvalid(this.emailInput);
		expect(isInvalid).toBe(true);

		// Also verify there's a validation message
		const message = await this.getInputValidationMessage(this.emailInput);
		expect(message.length).toBeGreaterThan(0);
	}

	/**
	 * Assert that the password input field is invalid.
	 * Note: This should be called after attempting to submit the form (e.g., after calling signUp).
	 * The form submission attempt triggers the browser's native validation.
	 */
	async assertPasswordInputIsInvalid(): Promise<void> {
		await this.ensureValidationChecked(this.passwordInput);
		const isInvalid = await this.isInputInvalid(this.passwordInput);
		expect(isInvalid).toBe(true);

		// Also verify there's a validation message
		const message = await this.getInputValidationMessage(this.passwordInput);
		expect(message.length).toBeGreaterThan(0);
	}

	/**
	 * Assert that a specific field shows a validation error.
	 * This is a more flexible method that can check any field.
	 * Note: This should be called after attempting to submit the form.
	 * @param field The field to check ('name', 'email', or 'password')
	 */
	async assertFieldIsInvalid(field: 'name' | 'email' | 'password'): Promise<void> {
		let inputLocator: ReturnType<typeof this.page.getByTestId>;
		switch (field) {
			case 'name':
				inputLocator = this.nameInput;
				break;
			case 'email':
				inputLocator = this.emailInput;
				break;
			case 'password':
				inputLocator = this.passwordInput;
				break;
		}

		await this.ensureValidationChecked(inputLocator);
		const isInvalid = await this.isInputInvalid(inputLocator);
		expect(isInvalid).toBe(true);

		// Also verify there's a validation message
		const message = await this.getInputValidationMessage(inputLocator);
		expect(message.length).toBeGreaterThan(0);
	}
}
