<script lang="ts">
export let className = 'size-8';
export let src = '/static/favicon.png';

$: imageSrc =
	typeof src === 'string' && src.trim() !== '' ? src : '/static/favicon.png';
</script>

<img
	src={imageSrc}
	class=" {className} object-cover rounded-full -translate-y-[1px]"
	alt="profile"
	draggable="false"
/>
