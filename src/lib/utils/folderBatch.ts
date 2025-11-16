// Shared batching service for folder expanded state updates
let folderUpdateBatch = new Map<string, boolean>();
let folderUpdateTimeout: ReturnType<typeof setTimeout> | null = null;
let batchUpdateFunction: ((updates: Array<{ id: string; isExpanded: boolean }>) => Promise<void>) | null = null;

export function setBatchUpdateFunction(
	fn: (updates: Array<{ id: string; isExpanded: boolean }>) => Promise<void>
) {
	batchUpdateFunction = fn;
}

export function scheduleFolderUpdate(folderId: string, isExpanded: boolean) {
	folderUpdateBatch.set(folderId, isExpanded);

	if (folderUpdateTimeout) {
		clearTimeout(folderUpdateTimeout);
	}

	folderUpdateTimeout = setTimeout(async () => {
		if (folderUpdateBatch.size > 0 && batchUpdateFunction) {
			const updates = Array.from(folderUpdateBatch.entries()).map(([id, expanded]) => ({
				id,
				isExpanded: expanded
			}));

			folderUpdateBatch.clear();

			try {
				await batchUpdateFunction(updates);
			} catch (error) {
				console.error('Failed to batch update folder expanded states:', error);
				throw error; // Let the caller handle fallback
			}
		}
	}, 500);
}

export function flushFolderUpdates() {
	if (folderUpdateTimeout) {
		clearTimeout(folderUpdateTimeout);
		folderUpdateTimeout = null;
	}
	
	if (folderUpdateBatch.size > 0 && batchUpdateFunction) {
		const updates = Array.from(folderUpdateBatch.entries()).map(([id, expanded]) => ({
			id,
			isExpanded: expanded
		}));

		folderUpdateBatch.clear();
		return batchUpdateFunction(updates);
	}
	
	return Promise.resolve();
}

