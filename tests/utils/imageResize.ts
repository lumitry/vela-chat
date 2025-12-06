import type { Page } from '@playwright/test';

/**
 * Resizes an image to 250x250 using the browser's canvas API, matching the frontend logic.
 * This uses the same algorithm as ModelEditor.svelte to ensure exact matching.
 *
 * @param page - The Playwright page object
 * @param imageBuffer - The original image as a Buffer
 * @returns A promise that resolves to the resized image as a Buffer
 */
export async function resizeImageTo250x250(page: Page, imageBuffer: Buffer): Promise<Buffer> {
	// Convert buffer to base64 data URL
	const base64Image = imageBuffer.toString('base64');
	const mimeType = 'image/png'; // Assuming PNG, could be detected from buffer
	const dataUrl = `data:${mimeType};base64,${base64Image}`;

	// Use browser's canvas API to resize (matching frontend logic exactly)
	const resizedDataUrl = await page.evaluate(
		(dataUrl: string) => {
			return new Promise<string>((resolve, reject) => {
				const img = new Image();
				img.onload = function () {
					const canvas = document.createElement('canvas');
					const ctx = canvas.getContext('2d');

					if (!ctx) {
						reject(new Error('Could not get canvas context'));
						return;
					}

					// Calculate the aspect ratio of the image
					const aspectRatio = img.width / img.height;

					// Calculate the new width and height to fit within 250x250
					let newWidth: number, newHeight: number;
					if (aspectRatio > 1) {
						newWidth = 250 * aspectRatio;
						newHeight = 250;
					} else {
						newWidth = 250;
						newHeight = 250 / aspectRatio;
					}

					// Set the canvas size
					canvas.width = 250;
					canvas.height = 250;

					// Calculate the position to center the image
					const offsetX = (250 - newWidth) / 2;
					const offsetY = (250 - newHeight) / 2;

					// Draw the image on the canvas
					ctx.drawImage(img, offsetX, offsetY, newWidth, newHeight);

					// Get the base64 representation of the compressed image
					const compressedSrc = canvas.toDataURL();
					resolve(compressedSrc);
				};
				img.onerror = (error) => reject(error);
				img.src = dataUrl;
			});
		},
		dataUrl
	);

	// Convert data URL back to Buffer
	const base64Data = resizedDataUrl.split(',')[1];
	return Buffer.from(base64Data, 'base64');
}

