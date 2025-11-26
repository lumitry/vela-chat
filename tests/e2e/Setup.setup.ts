import { test } from '@playwright/test';
import { OnboardingPage } from '../pages/OnboardingPage';
import { AuthPage } from '../pages/AuthPage';
import { SHARED_USERS } from '../data/users';
import { HomePage } from '../pages/HomePage';
import { AdminSettingsGeneralTab } from '../pages/Admin/AdminSettingsGeneralTab';
import { AdminSettingsConnectionsTab } from '../pages/Admin/AdminSettingsConnectionsTab';
import { MINI_MEDIATOR_OLLAMA, MINI_MEDIATOR_OPENAI } from '../data/endpoints';
import { AdminSettingsDocumentsTab } from '../pages/Admin/AdminSettingsDocumentsTab';
import { MINI_MEDIATOR_EMBEDDING_OPENAI } from '../data/miniMediatorModels';

/**
 * Setup test that runs before all other tests.
 *
 * This test assumes:
 * - The app is already running
 * - The database is empty (only schema, no data)
 *
 * It performs:
 * 1. Goes through the onboarding flow (first user becomes admin)
 * 2. Configures initial settings (model connections, etc.)
 *
 * To skip this in local development, set SKIP_SETUP=true:
 *   SKIP_SETUP=true npx playwright test
 */
test('setup test environment via onboarding', async ({ page }) => {
	// Skip setup if SKIP_SETUP env var is set (for local dev)
	if (process.env.SKIP_SETUP === 'true') {
		test.skip();
		return;
	}

	console.log('🔧 Setting up test environment via onboarding...');

	// 1. Start from onboarding (first user becomes admin)
	console.log('📝 Starting onboarding flow...');
	await page.goto('/');

	const onboardingPage = new OnboardingPage(page);
	await onboardingPage.clickGetStartedButton();
	const authPage = new AuthPage(page);
	await authPage.signUp(SHARED_USERS.preExistingAdmin);
	await authPage.toast.assertToastIsVisible('success');

	// 2. Configure initial settings via admin panel
	console.log('⚙️  Configuring initial settings...');
	const homePage = new HomePage(page);
	await homePage.clickUserMenuButton();
	await homePage.userMenu.clickAdminPanel();
	const adminSettings = new AdminSettingsGeneralTab(page);
	await adminSettings.setDefaultUserRole('admin');
	await adminSettings.setEnableNewSignUps(true);
	await adminSettings.clickSaveButton();
	await adminSettings.toast.assertToastIsVisible('success');

	console.log('📝 Setting up model connections...');
	// note: this could be done via environment variables, but those are less reproducible for others, so I'm sticking to this for now.
	await adminSettings.clickConnectionsTabButton();
	const adminSettingsConnectionsTab = new AdminSettingsConnectionsTab(page);

	await adminSettingsConnectionsTab.setEnableOpenAISwitch(true);
	await adminSettingsConnectionsTab.setOpenAIConnection(MINI_MEDIATOR_OPENAI, 0);

	await adminSettingsConnectionsTab.setEnableOllamaSwitch(true);
	await adminSettingsConnectionsTab.setOllamaConnection(MINI_MEDIATOR_OLLAMA, 0);

	await adminSettingsConnectionsTab.setEnableDirectConnectionsSwitch(true);
	await adminSettingsConnectionsTab.clickSaveButton();
	await adminSettingsConnectionsTab.toast.assertToastIsVisible('success');

	// - Set default embedding model to Mini-Mediator
	console.log('📝 Setting default embedding model to Mini-Mediator...');
	await adminSettingsConnectionsTab.clickDocumentsTabButton();
	const adminSettingsDocumentsTab = new AdminSettingsDocumentsTab(page);
	await adminSettingsDocumentsTab.setEmbeddingModel({
		engine: 'openai',
		model: MINI_MEDIATOR_EMBEDDING_OPENAI.name,
		url: MINI_MEDIATOR_EMBEDDING_OPENAI.endpoint.url,
		batchSize: 1 // TODO at some point in the future, we'll need to test different batch sizes with mini-mediator too...
	});
	await adminSettingsDocumentsTab.clickSaveButton();
	await adminSettingsDocumentsTab.toast.assertToastIsVisible('success');

	// TODO: Set task models to Mini-Mediator
	// I don't have time to handle this today...
	// await adminSettingsConnectionsTab.clickInterfaceTabButton();
	// const adminSettingsInterfaceTab = new AdminSettingsInterfaceTab(page);
	// await adminSettingsInterfaceTab.setInternalTaskModel(MINI_MEDIATOR_TASK.name);
	// await adminSettingsInterfaceTab.setExternalTaskModel(MINI_MEDIATOR_TASK.name);
	// await adminSettingsInterfaceTab.clickSaveButton();
	// await adminSettingsInterfaceTab.toast.assertToastIsVisible('success');

	console.log('✅ Test environment setup complete!');
});
