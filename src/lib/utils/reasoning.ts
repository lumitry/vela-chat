import type { Model } from '$lib/stores';

export interface ReasoningBehavior {
	type: 'change_model' | 'set_effort' | 'set_max_tokens' | 'toggle_think_prompt';
	target_model?: string;
	reasoning_effort?: 'low' | 'medium' | 'high';
	max_tokens?: number;
	reasoning_prompt?: string;
	reasoning_system_prompt?: string;
}

export interface ModelDetails {
	response_structure?: 'Classical' | 'Native Chain-of-Thought Reasoning' | 'Hybrid CoT Reasoning';
	price_per_1m_input_tokens?: number;
	price_per_1m_output_tokens?: number;
	max_context_length?: number;
	price_per_1k_images?: number;
	reasoning_behavior?: string; // This is a simple string like 'change_model', 'set_effort', etc.
	reasoning_target_model?: string;
	reasoning_effort?: string | null;
	reasoning_max_tokens?: number | null;
}

export interface ReasoningState {
	isThinkingMode: boolean;
	baseModel: string;
	reasoningModel?: string;
	originalModelDetails?: ModelDetails;
}

// Helper to safely access model details from meta
function getModelDetails(model: Model): ModelDetails | undefined {
	return (model?.info?.meta as any)?.model_details;
}

// Helper to check if a model is a reasoning target for another model
function isReasoningTargetForAnotherModel(model: Model, availableModels: Model[]): boolean {
	return availableModels.some((m) => {
		const details = getModelDetails(m);
		return (
			details?.reasoning_behavior === 'change_model' && details.reasoning_target_model === model.id
		);
	});
}

/**
 * Determines if a model supports reasoning based on its response structure and reasoning behavior
 */
export function isReasoningCapable(model: Model, availableModels: Model[]): boolean {
	const modelDetails = getModelDetails(model);

	// Check if model has reasoning behavior configured
	if (modelDetails?.reasoning_behavior && modelDetails.reasoning_behavior !== 'none') {
		// For model switching: check if target model exists
		if (modelDetails.reasoning_behavior === 'change_model') {
			if (Boolean(modelDetails.reasoning_target_model)) {
				return true;
			}
		}

		// For reasoning effort/max tokens: check if model has non-classical response
		if (
			modelDetails.reasoning_behavior === 'set_effort' ||
			modelDetails.reasoning_behavior === 'set_max_tokens'
		) {
			if (
				modelDetails.response_structure === 'Native Chain-of-Thought Reasoning' ||
				modelDetails.response_structure === 'Hybrid CoT Reasoning'
			) {
				return true;
			}
		}

		// For prompt toggles: any response structure can work
		if (modelDetails.reasoning_behavior === 'toggle_think_prompt') {
			return true; // We'll assume this can work with any model if configured
		}
	}

	// Check if the current model is a reasoning target for another model.
	if (isReasoningTargetForAnotherModel(model, availableModels)) {
		return true;
	}

	// Show if the model has a native or hybrid reasoning structure, even without a specific behavior
	if (
		modelDetails?.response_structure === 'Native Chain-of-Thought Reasoning' ||
		modelDetails?.response_structure === 'Hybrid CoT Reasoning'
	) {
		return true;
	}

	return false;
}

/**
 * Checks if reasoning mode should be enabled/illuminated for current model
 */
export function shouldIlluminateThinking(
	model: Model,
	availableModels: Model[],
	currentReasoningState?: ReasoningState
): boolean {
	// If we're in thinking mode, illuminate the button if we're on the reasoning model
	if (currentReasoningState?.isThinkingMode) {
		// Check if the current model is the reasoning model
		const isCurrentModelTheReasoningModel = model.id === currentReasoningState.reasoningModel;
		
		if (isCurrentModelTheReasoningModel) {
			// For cyclical setups, ensure we only illuminate if it's actually a CoT model
			const currentModelDetails = getModelDetails(model);
			const isCurrentModelCoT = currentModelDetails?.response_structure === 'Native Chain-of-Thought Reasoning' ||
			                         currentModelDetails?.response_structure === 'Hybrid CoT Reasoning';
			const isCurrentModelClassical = currentModelDetails?.response_structure === 'Classical';
			
			// If it's explicitly marked as Classical, don't illuminate (handles cyclical case)
			// If it's CoT or undefined/null (default), illuminate (handles normal case)
			return !isCurrentModelClassical;
		}
		
		return false;
	}

	const modelDetails = getModelDetails(model);

	if (!modelDetails) {
		return false;
	}

	// If model has reasoning behavior configured, check if it should be illuminated
	if (modelDetails.reasoning_behavior && modelDetails.reasoning_behavior !== 'none') {
		// For model switching behavior, illuminate based on response structure
		if (modelDetails.reasoning_behavior === 'change_model') {
			// Illuminate if the model is inherently a reasoning model
			return modelDetails.response_structure === 'Native Chain-of-Thought Reasoning';
		}

		// For other behaviors, illuminate if model has non-classical response
		if (
			modelDetails.reasoning_behavior === 'set_effort' ||
			modelDetails.reasoning_behavior === 'set_max_tokens' ||
			modelDetails.reasoning_behavior === 'toggle_think_prompt'
		) {
			return (
				modelDetails.response_structure === 'Native Chain-of-Thought Reasoning' ||
				modelDetails.response_structure === 'Hybrid CoT Reasoning'
			);
		}
	}

	// If no reasoning behavior but has CoT response, illuminate (native CoT model)
	if (modelDetails.response_structure === 'Native Chain-of-Thought Reasoning') {
		return true;
	}

	// If the model is a reasoning target for another model, only illuminate if it's actually a CoT model
	if (isReasoningTargetForAnotherModel(model, availableModels) && modelDetails) {
		const responseStructure = modelDetails.response_structure as string;
		return responseStructure === 'Native Chain-of-Thought Reasoning' ||
		       responseStructure === 'Hybrid CoT Reasoning';
	}

	return false;
}

/**
 * Checks if the thinking button should be clickable
 */
export function isThinkingClickable(model: Model, availableModels: Model[]): boolean {
	const modelDetails = getModelDetails(model);

	// If model has reasoning behavior configured, it's clickable
	if (modelDetails?.reasoning_behavior && modelDetails.reasoning_behavior !== 'none') {
		return true;
	}

	// Check if the current model is a reasoning target for another model.
	if (isReasoningTargetForAnotherModel(model, availableModels)) {
		return true;
	}

	// If it's a Native CoT or Hybrid CoT response model without reasoning behavior,
	// it should be illuminated but not clickable (case 4 from the docs)
	if (
		modelDetails?.response_structure === 'Native Chain-of-Thought Reasoning' ||
		modelDetails?.response_structure === 'Hybrid CoT Reasoning'
	) {
		return false; // Illuminated but not clickable
	}

	return false;
}

/**
 * Gets the target model for reasoning mode.
 * Also handles finding the base and target models if the current model is a reasoning model.
 */
export function getReasoningTargetModel(
	model: Model,
	availableModels: Model[]
): { base: Model; target: Model } | undefined {
	const modelDetails = getModelDetails(model);

	// Case 1: The current model has a `reasoning_target_model` defined.
	if (
		modelDetails?.reasoning_behavior === 'change_model' &&
		modelDetails.reasoning_target_model
	) {
		const targetModel = availableModels.find((m) => m.id === modelDetails.reasoning_target_model);
		if (targetModel) {
			return { base: model, target: targetModel };
		}
	}

	// Case 2: The current model is the `reasoning_target_model` for another model.
	const baseModel = availableModels.find((m) => {
		const details = getModelDetails(m);
		return details?.reasoning_behavior === 'change_model' && details.reasoning_target_model === model.id;
	});

	if (baseModel) {
		// The current model is the target, so we are switching back to the base.
		// But we need to determine which one is actually the reasoning model (CoT) and which is the base (classical)
		const currentModelDetails = getModelDetails(model);
		const baseModelDetails = getModelDetails(baseModel);
		
		// The reasoning model should be the one with CoT response structure
		if (currentModelDetails?.response_structure === 'Native Chain-of-Thought Reasoning' ||
		    currentModelDetails?.response_structure === 'Hybrid CoT Reasoning') {
			// Current model is the CoT model, so it should be the target (reasoning model)
			return { base: baseModel, target: model };
		} else if (baseModelDetails?.response_structure === 'Native Chain-of-Thought Reasoning' ||
		          baseModelDetails?.response_structure === 'Hybrid CoT Reasoning') {
			// Base model is the CoT model, so it should be the target (reasoning model)
			return { base: model, target: baseModel };
		} else {
			// Neither has CoT structure, fall back to original logic
			return { base: baseModel, target: model };
		}
	}

	// Case 3: Non-switching behaviors (e.g., set_effort). Target is the model itself.
	if (modelDetails?.reasoning_behavior && modelDetails.reasoning_behavior !== 'change_model') {
		return { base: model, target: model };
	}

	return undefined;
}

/**
 * Creates the reasoning state when entering thinking mode
 */
export function createReasoningState(baseModel: Model, targetModel: Model): ReasoningState {
	return {
		isThinkingMode: true,
		baseModel: baseModel.id,
		reasoningModel: targetModel.id,
		originalModelDetails: getModelDetails(baseModel)
	};
}

/**
 * Updates model configuration for reasoning mode
 */
export function applyReasoningConfiguration(model: Model, reasoningState: ReasoningState): Partial<Model> {
	const modelDetails = getModelDetails(model);
	if (!modelDetails?.reasoning_behavior) {
		return {};
	}

	const updates: any = {};

	// For reasoning effort, update the model configuration
    // TODO: does this work? implement it in MessageInput.svelte
    // I'm specifically worried about making sure models where the user has already set the model's default effort (e.g. to "high"):
    // 1) get seen as reasoning models
    // 2) get the correct reasoning effort applied (e.g. None(AKA null))
    // For example, will this require checking the model's default reasoning effort in shouldIlluminateThinking etc. to see if it's set to reason by default?
    // In an ideal world, users would create workspace models with the reasoning effort set to whatever they wanted it to be and just use the switch model behavior instead, but that's so much work. This would be a far simpler UX.
	if (modelDetails.reasoning_behavior === 'set_effort' && modelDetails.reasoning_effort) {
		// This would typically map to specific model parameters
		updates.reasoning_effort = modelDetails.reasoning_effort;
	}

	// For max tokens, update the model configuration
	if (modelDetails.reasoning_behavior === 'set_max_tokens' && modelDetails.reasoning_max_tokens) {
		updates.max_tokens = modelDetails.reasoning_max_tokens;
	}

	// For prompt toggles, we'll handle this in the message creation logic
	// as it affects the prompt/system prompt sent to the model

	return updates;
}

/**
 * Modifies the prompt for reasoning mode if needed
 */
export function applyReasoningPrompt(originalPrompt: string, model: Model, isThinkingMode: boolean): string {
	if (!isThinkingMode) {
		return originalPrompt;
	}

	const modelDetails = getModelDetails(model);
	if (!modelDetails?.reasoning_behavior) {
		return originalPrompt;
	}

	if (modelDetails.reasoning_behavior === 'toggle_think_prompt') {
        // TODO: does this work? implement it in MessageInput.svelte
		return `${originalPrompt}\n/think`;
	}

	return originalPrompt;
}

/**
 * Modifies the system prompt for reasoning mode if needed
 */
// TODO: figure out if we're going to support system prompt changes in reasoning mode, I'm still unsure about this (implementing this without breaking the user's system prompt, the chat's system prompt, the model's default system prompt, etc. is tricky and would require far more testing than I can handle atm)
// export function applyReasoningSystemPrompt(originalSystem: string, model: Model, isThinkingMode: boolean): string {
// 	if (!isThinkingMode) {
// 		return originalSystem;
// 	}

// 	const modelDetails = getModelDetails(model);
// 	if (!modelDetails?.reasoning_behavior) {
// 		return originalSystem;
// 	}

// 	const behavior = modelDetails.reasoning_behavior;

// 	if (behavior.type === 'system_prompt_toggle' && behavior.reasoning_system_prompt) {
// 		return behavior.reasoning_system_prompt;
// 	}

// 	return originalSystem;
// }

/**
 * Persists reasoning state to chat history
 */
export function persistReasoningState(history: any, reasoningState: ReasoningState | null): void {
	if (history) {
		if (reasoningState) {
			history.reasoningState = reasoningState;
		} else {
			delete history.reasoningState;
		}
	}
}

/**
 * Loads reasoning state from chat history
 */
export function loadReasoningState(history: any): ReasoningState | null {
	return history?.reasoningState || null;
}
