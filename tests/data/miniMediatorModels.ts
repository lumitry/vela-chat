import {
	MINI_MEDIATOR_OLLAMA,
	MINI_MEDIATOR_OPENAI,
	type OllamaEndpoint,
	type OpenAIEndpoint
} from './endpoints';

export class MiniMediatorModel {
	id: string;
	name: string;
	endpoint: OpenAIEndpoint | OllamaEndpoint;

	/**
	 * Represents a Mini-Mediator model.
	 *
	 * @param id - The ID of the model, NOT including any endpoint prefix!
	 * @param name - The 'pretty' name of the model, e.g. "Mini-Mediator Embedding OpenAI v1".
	 * @param endpoint - The endpoint that the model is hosted on.
	 */
	constructor(id: string, name: string, endpoint: OpenAIEndpoint | OllamaEndpoint) {
		this.id = id;
		this.name = name;
		this.endpoint = endpoint;
	}

	/**
	 * Creates a Mini-Mediator model from an ID and an endpoint.
	 *
	 * @param id - The ID of the model, NOT including any endpoint prefix!
	 * @param endpoint - The endpoint that the model is hosted on.
	 * @returns A new Mini-Mediator model with the name being the same as the ID.
	 */
	static buildFromIdAndEndpoint(
		id: string,
		endpoint: OpenAIEndpoint | OllamaEndpoint
	): MiniMediatorModel {
		return new MiniMediatorModel(id, id, endpoint);
	}

	/**
	 * Gets the full ID with the endpoint prefix, if it exists.
	 * For example, if the endpoint prefix is `ollama` and the ID is `mini-mediator:mirror`,
	 * the full ID will be `ollama.mini-mediator:mirror`.
	 *
	 * If the endpoint prefix is not set, the full ID will be the same as the ID.
	 *
	 * This is useful for selecting the model in the UI!
	 *
	 * @returns The full ID with the endpoint prefix, if it exists.
	 */
	public getFullIdWithEndpointPrefix(): string {
		if (this.endpoint.prefix) {
			return `${this.endpoint.prefix}.${this.id}`;
		}
		return this.id;
	}
}

export const MINI_MEDIATOR_EMBEDDING_OPENAI: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint(
		'mini-mediator-embedding-openai-v1',
		MINI_MEDIATOR_OPENAI
	);

export const MINI_MEDIATOR_EMBEDDING_OLLAMA: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint(
		'mini-mediator-embedding-ollama-v1',
		MINI_MEDIATOR_OLLAMA
	);

export const MINI_MEDIATOR_MIRROR_OPENAI: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint('mini-mediator:mirror', MINI_MEDIATOR_OPENAI);

export const MINI_MEDIATOR_MIRROR_OLLAMA: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint('mini-mediator:mirror', MINI_MEDIATOR_OLLAMA);

export const MINI_MEDIATOR_TASK_OLLAMA: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint('mini-mediator:task', MINI_MEDIATOR_OLLAMA);

export const MINI_MEDIATOR_TASK_OPENAI: MiniMediatorModel =
	MiniMediatorModel.buildFromIdAndEndpoint('mini-mediator:task', MINI_MEDIATOR_OPENAI);
