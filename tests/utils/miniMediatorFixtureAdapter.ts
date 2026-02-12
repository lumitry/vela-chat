import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

export interface MiniMediatorFixture {
	model: string;
	created?: number;
	defaults?: FixtureStreamingDefaults & Record<string, unknown>;
	scenarios: Scenario[];
}

export interface Scenario {
	name: string;
	match: Match;
	response?: Response;
	error?: ErrorResponse;
	usage?: Record<string, unknown>;
	streaming?: ScenarioStreamingConfig;
	metadata?: Record<string, unknown>;
}

export interface Match {
	type: 'exact' | 'regex';
	role: string;
	text: string;
}

export interface Response {
	message: string;
	think?: string | null;
	tool_calls?: unknown[];
	attachments?: unknown[];
}

export interface ErrorResponse {
	status_code: number;
	type: string;
	message: string;
	retry_after?: number;
}

/**
 * Shape of streaming config fields we care about from fixtures.defaults
 */
interface FixtureStreamingDefaults {
	profile?: string;
	chars_per_token?: number;
	chunk_batch_size?: number;
	target_tokens_per_second?: number;
	pause_profile?: PauseProfileRaw;
}

/**
 * Shape of per-scenario streaming overrides we care about.
 */
export interface ScenarioStreamingConfig {
	profile?: string;
	chars_per_token?: number;
	chunk_batch_size?: number;
	target_tokens_per_second?: number;
	pause_profile?: PauseProfileRaw;
}

type PauseProfileEntry = {
	after_chunk?: number;
	seconds?: number;
};

// Can be either an array of {after_chunk, seconds} or an object with
// before_first_chunk / mid_stream / after_final_chunk shape.
type PauseProfileRaw =
	| PauseProfileEntry[]
	| {
			before_first_chunk?: number;
			mid_stream?: PauseProfileEntry[];
			after_final_chunk?: number;
	  };

interface StreamingConfig {
	profile: string;
	charsPerToken: number;
	chunkBatchSize: number;
	targetTokensPerSecond?: number;
	pauseDurationsSeconds: number[];
}

export class MiniMediatorFixtureAdapter {
	private fixture: MiniMediatorFixture | null = null;
	private fixturePath: string;

	constructor(fixturePath?: string) {
		// Default path relative to this file:
		// tests/utils/miniMediatorFixtureAdapter.ts
		//   -> ../mocks/mini-mediator/fixtures/models/deterministic.json
		const __filename = fileURLToPath(import.meta.url);
		const __dirname = path.dirname(__filename);

		const defaultPath = path.resolve(
			__dirname,
			'../mocks/mini-mediator/fixtures/models/deterministic.json'
		);

		this.fixturePath = fixturePath ? path.resolve(fixturePath) : defaultPath;
	}

	private loadFixtureIfNeeded(): MiniMediatorFixture {
		if (this.fixture) {
			return this.fixture;
		}

		try {
			const fileContent = fs.readFileSync(this.fixturePath, 'utf-8');
			this.fixture = JSON.parse(fileContent) as MiniMediatorFixture;
		} catch (error) {
			// In some environments (e.g., certain linting setups), the fixture path may not be
			// resolvable in the same way as during Playwright runs. Instead of throwing here and
			// breaking tooling, fall back to an empty fixture. Tests that rely on real fixtures
			// will still fail with a clear "scenario not found" error.
			// eslint-disable-next-line no-console
			console.warn(
				`MiniMediatorFixtureAdapter: failed to load fixture at ${this.fixturePath}:`,
				error
			);
			this.fixture = { model: 'unknown', scenarios: [] };
		}

		return this.fixture;
	}

	public getScenario(name: string): Scenario {
		const fixture = this.loadFixtureIfNeeded();
		const scenario = fixture.scenarios.find((s) => s.name === name);
		if (!scenario) {
			throw new Error(`Scenario with name '${name}' not found in fixture.`);
		}
		return scenario;
	}

	public getScenarioInput(name: string): string {
		const scenario = this.getScenario(name);
		return scenario.match.text;
	}

	public getScenarioResponse(name: string): string {
		const scenario = this.getScenario(name);
		if (!scenario.response) {
			throw new Error(`Scenario '${name}' does not have a response.`);
		}
		return scenario.response.message;
	}

	private getStreamingConfigForScenario(scenario: Scenario): StreamingConfig {
		const fixture = this.loadFixtureIfNeeded();
		const defaults = (fixture.defaults ?? {}) as FixtureStreamingDefaults;
		const streaming = (scenario.streaming ?? {}) as ScenarioStreamingConfig;

		const profile = streaming.profile ?? defaults.profile ?? 'token';
		const charsPerToken = streaming.chars_per_token ?? defaults.chars_per_token ?? 4;
		const chunkBatchSize = streaming.chunk_batch_size ?? defaults.chunk_batch_size ?? 10;
		const targetTokensPerSecond =
			streaming.target_tokens_per_second ?? defaults.target_tokens_per_second;

		const pauseProfileRaw: PauseProfileRaw | undefined =
			streaming.pause_profile ?? defaults.pause_profile;

		const pauseDurationsSeconds: number[] = [];

		if (pauseProfileRaw) {
			if (Array.isArray(pauseProfileRaw)) {
				for (const entry of pauseProfileRaw) {
					if (typeof entry?.seconds === 'number') {
						pauseDurationsSeconds.push(entry.seconds);
					}
				}
			} else if (typeof pauseProfileRaw === 'object') {
				const maybeSeconds: number[] = [];
				if (typeof pauseProfileRaw.before_first_chunk === 'number') {
					maybeSeconds.push(pauseProfileRaw.before_first_chunk);
				}
				if (typeof pauseProfileRaw.after_final_chunk === 'number') {
					maybeSeconds.push(pauseProfileRaw.after_final_chunk);
				}
				if (Array.isArray(pauseProfileRaw.mid_stream)) {
					for (const mid of pauseProfileRaw.mid_stream) {
						if (typeof mid?.seconds === 'number') {
							maybeSeconds.push(mid.seconds);
						}
					}
				}
				pauseDurationsSeconds.push(...maybeSeconds);
			}
		}

		return {
			profile,
			charsPerToken,
			chunkBatchSize,
			targetTokensPerSecond,
			pauseDurationsSeconds
		};
	}

	private chunkResponseByStreamingConfig(message: string, config: StreamingConfig): string[] {
		const { profile, charsPerToken, chunkBatchSize } = config;

		// From fixtures/README.md:
		// - profile "token": ~4-char slices
		// - profile "chunky": batches of N token-slices
		//
		// We approximate the server's chunk planner here:
		// - For "token", each chunk is a single token slice (charsPerToken characters).
		// - For "chunky", each chunk is chunkBatchSize token slices.
		let tokensPerChunk: number;

		if (profile === 'token') {
			tokensPerChunk = 1;
		} else if (profile === 'chunky') {
			tokensPerChunk = chunkBatchSize > 0 ? chunkBatchSize : 10;
		} else {
			// Fallback: treat as token-based with configurable batch size.
			tokensPerChunk = chunkBatchSize > 0 ? chunkBatchSize : 1;
		}

		const charsPerChunk = Math.max(1, charsPerToken * tokensPerChunk);

		const chunks: string[] = [];
		for (let i = 0; i < message.length; i += charsPerChunk) {
			chunks.push(message.slice(i, i + charsPerChunk));
		}

		return chunks;
	}

	public getScenarioResponseChunk(name: string, chunkIndex: number): string {
		const scenario = this.getScenario(name);
		if (!scenario.response) {
			throw new Error(`Scenario '${name}' does not have a response.`);
		}
		if (chunkIndex < 0) {
			throw new Error(`Chunk index must be non-negative. Received: ${chunkIndex}`);
		}

		const message = scenario.response.message;
		const streamingConfig = this.getStreamingConfigForScenario(scenario);
		const chunks = this.chunkResponseByStreamingConfig(message, streamingConfig);

		if (chunkIndex >= chunks.length) {
			throw new Error(
				`Chunk index ${chunkIndex} is out of range for scenario '${name}'. Total chunks: ${chunks.length}.`
			);
		}

		return chunks[chunkIndex];
	}

	public getMaxPauseSeconds(name: string): number {
		const scenario = this.getScenario(name);
		const config = this.getStreamingConfigForScenario(scenario);
		if (!config.pauseDurationsSeconds.length) {
			return 0;
		}
		return Math.max(...config.pauseDurationsSeconds);
	}

	public getRecommendedWarmupMs(name: string, desiredChunks: number = 2): number {
		const scenario = this.getScenario(name);
		const config = this.getStreamingConfigForScenario(scenario);

		const tps = config.targetTokensPerSecond ?? 50; // sane default

		let tokensPerChunk: number;
		if (config.profile === 'chunky') {
			tokensPerChunk = config.chunkBatchSize > 0 ? config.chunkBatchSize : 10;
		} else {
			// "token" or any other profile: one logical token per chunk
			tokensPerChunk = 1;
		}

		const tokensNeeded = Math.max(1, tokensPerChunk * desiredChunks);
		const seconds = tokensNeeded / tps;

		// Convert to ms and add a safety factor; clamp to a reasonable range.
		const rawMs = seconds * 1000;
		const withSafetyFactor = rawMs * 2; // 2x safety

		// Never go below 100ms, never above 1000ms for this "warmup" wait.
		return Math.min(Math.max(withSafetyFactor, 100), 1000);
	}
}

// Export a singleton instance for convenience
export const deterministicFixture = new MiniMediatorFixtureAdapter();
