<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { get } from 'svelte/store';

	import { getChatById } from '$lib/apis/chats';
	import { createMessagesList } from '$lib/utils';
	import { theme } from '$lib/stores';

	export let chatId: string;

	const dispatch = createEventDispatcher();

	type SaveAsFn = (data: Blob | File, filename?: string, options?: unknown) => void;

	async function getSaveAs(): Promise<SaveAsFn> {
		const mod = (await import('file-saver')) as Record<string, unknown>;
		if (typeof mod.saveAs === 'function') {
			return mod.saveAs as SaveAsFn;
		}
		if (typeof mod.default === 'function') {
			return mod.default as SaveAsFn;
		}
		if (
			mod.default &&
			typeof mod.default === 'object' &&
			typeof (mod.default as Record<string, unknown>).saveAs === 'function'
		) {
			return (mod.default as Record<string, SaveAsFn>).saveAs;
		}
		throw new Error('file-saver module did not expose saveAs');
	}

	async function exportJson() {
		try {
			const saveAs = await getSaveAs();
			const chat = await getChatById(localStorage.token, chatId, undefined, true);
			if (!chat) {
				toast.error('Failed to load chat.');
				return;
			}
			const blob = new Blob([JSON.stringify([chat])], { type: 'application/json' });
			saveAs(blob, `chat-export-${Date.now()}.json`);
			toast.success('Chat exported as JSON.');
			dispatch('close');
		} catch (error) {
			console.error(error);
			toast.error('Failed to export chat.');
		}
	}

	async function exportText() {
		try {
			const saveAs = await getSaveAs();
			const chat = await getChatById(localStorage.token, chatId);
			if (!chat) {
				toast.error('Failed to load chat.');
				return;
			}

			const history = chat.chat.history;
			const messages = createMessagesList(history, history.currentId);
			const chatText = messages
				.reduce<string>((acc, message) => {
					return `${acc}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
				}, '')
				.trim();

			const blob = new Blob([chatText], { type: 'text/plain' });
			saveAs(blob, `chat-${chat.chat.title}.txt`);
			toast.success('Chat exported as text.');
			dispatch('close');
		} catch (error) {
			console.error(error);
			toast.error('Failed to export chat.');
		}
	}

	async function exportPdf() {
		try {
			const chat = await getChatById(localStorage.token, chatId);
			if (!chat) {
				toast.error('Failed to load chat.');
				return;
			}

			const containerElement = document.getElementById('messages-container');
			if (!containerElement) {
				toast.error('Messages container not found.');
				return;
			}

			const html2canvasModule = (await import('html2canvas-pro')) as { default?: unknown };
			const html2canvas = html2canvasModule.default;
			if (typeof html2canvas !== 'function') {
				throw new Error('html2canvas-pro did not expose a default function');
			}
			const jsPDFModule = (await import('jspdf')) as { default?: unknown };
			const JsPDF = jsPDFModule.default;
			if (typeof JsPDF !== 'function') {
				throw new Error('jspdf did not expose a default constructor');
			}
			const saveAs = await getSaveAs();

			const isDarkMode = get(theme)?.includes('dark');
			const virtualWidth = 1024;
			const virtualHeight = 1400;

			const clonedElement = containerElement.cloneNode(true) as HTMLElement;
			clonedElement.style.width = `${virtualWidth}px`;
			clonedElement.style.height = 'auto';

			document.body.appendChild(clonedElement);

			const canvas = await html2canvas(clonedElement, {
				backgroundColor: isDarkMode ? '#000' : '#fff',
				useCORS: true,
				scale: 2,
				width: virtualWidth,
				windowWidth: virtualWidth,
				windowHeight: virtualHeight
			});

			document.body.removeChild(clonedElement);

			const imgData = canvas.toDataURL('image/png');
			const pdf = new JsPDF('p', 'mm', 'a4');
			const imgWidth = 210;
			const pageHeight = 297;
			const imgHeight = (canvas.height * imgWidth) / canvas.width;
			let heightLeft = imgHeight;
			let position = 0;

			if (isDarkMode) {
				pdf.setFillColor(0, 0, 0);
				pdf.rect(0, 0, imgWidth, pageHeight, 'F');
			}

			pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
			heightLeft -= pageHeight;

			while (heightLeft > 0) {
				position -= pageHeight;
				pdf.addPage();
				if (isDarkMode) {
					pdf.setFillColor(0, 0, 0);
					pdf.rect(0, 0, imgWidth, pageHeight, 'F');
				}
				pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
				heightLeft -= pageHeight;
			}

			saveAs(pdf.output('blob'), `chat-${chat.chat.title}.pdf`);
			toast.success('Chat exported as PDF.');
			dispatch('close');
		} catch (error) {
			console.error('Error generating PDF', error);
			toast.error('Failed to export PDF.');
		}
	}
</script>

<div class="px-4 py-6 space-y-3">
	<div class="text-sm text-gray-700 dark:text-gray-300 font-medium">Export current chat as:</div>
	<div class="flex flex-col gap-2">
		<button
			type="button"
			class="text-left px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-850 text-sm"
			on:click={exportJson}
		>
			JSON (.json)
		</button>
		<button
			type="button"
			class="text-left px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-850 text-sm"
			on:click={exportText}
		>
			Plain text (.txt)
		</button>
		<button
			type="button"
			class="text-left px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-850 text-sm"
			on:click={exportPdf}
		>
			PDF document (.pdf)
		</button>
	</div>
	<div class="flex justify-end">
		<button
			type="button"
			class="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800"
			on:click={() => dispatch('close')}
		>
			Close
		</button>
	</div>
</div>
