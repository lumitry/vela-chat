import {
	MINI_MEDIATOR_OLLAMA,
	MINI_MEDIATOR_OPENAI,
	type OllamaEndpoint,
	type OpenAIEndpoint
} from './endpoints';

export type MiniMediatorModel = {
	name: string;
	endpoint: OpenAIEndpoint | OllamaEndpoint;
};

export const MINI_MEDIATOR_EMBEDDING_OPENAI: MiniMediatorModel = {
	name: 'mini-mediator-embedding-openai-v1',
	endpoint: MINI_MEDIATOR_OPENAI
};

export const MINI_MEDIATOR_EMBEDDING_OLLAMA: MiniMediatorModel = {
	name: 'mini-mediator-embedding-ollama-v1',
	endpoint: MINI_MEDIATOR_OLLAMA
};
