<script lang="ts">
	import { WEBUI_BASE_URL, getImageBaseUrl } from '$lib/constants';

	export let className = 'size-8';
	export let src = `${getImageBaseUrl('/static/favicon.png')}/static/favicon.png`;

	$: imageSrc =
		src === ''
			? `${getImageBaseUrl('/static/favicon.png')}/static/favicon.png`
			: src.startsWith(WEBUI_BASE_URL) ||
				  src.startsWith('https://www.gravatar.com/avatar/') ||
				  src.startsWith('data:') ||
				  src.startsWith('http://') ||
				  src.startsWith('https://')
				? src
				: src.startsWith('/')
					? `${getImageBaseUrl(src)}${src}`
					: `${getImageBaseUrl('/user.png')}/user.png`;
</script>

<img
	src={imageSrc}
	class=" {className} object-cover rounded-full -translate-y-[1px]"
	alt="profile"
	draggable="false"
/>
