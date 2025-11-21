<script lang="ts">
	interface Props {
		className?: string;
		src?: string;
	}

	let { className = 'size-8', src = '/static/favicon.png' }: Props = $props();

let imageSrc =
	$derived(typeof src === 'string' && src.trim() !== '' ? src : '/static/favicon.png');
</script>

<img
	src={imageSrc}
	class=" {className} object-cover rounded-full -translate-y-[1px]"
	alt="profile"
	draggable="false"
/>
