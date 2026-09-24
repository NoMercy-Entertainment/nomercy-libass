// -----------------------------------------------------------------------------
//  Copyright (c) NoMercy Entertainment
//
//  Licensed under the Apache License, Version 2.0. See LICENSE for details.
//
//  SPDX-License-Identifier: Apache-2.0
// -----------------------------------------------------------------------------
//
// The protocol half of the worker.
//
// The linked module exports libass's C entry points and nothing else, so a
// browser loading it has a wasm binary and no way to say "draw this cue". This
// is what the wrapper in packages/subtitles/nomercy-subtitle-octopus talks to, and it is
// deliberately the same shape as the events its WorkerBridge already handles:
// nm:ready, nm:error, nm:fonts-loaded.
//
// Rendering happens here rather than on the main thread because compositing a
// frame of ASS is a per-cue loop over bitmaps, and doing that between a
// video frame and its deadline is how subtitle overlays make players stutter.
//
// Linked with --extern-post-js, not --post-js: with MODULARIZE the latter is
// emitted INSIDE the module factory, so this would be waiting for the thing it
// lives in. The worker loaded, answered nothing, and read as a build that had
// produced no protocol at all.

/* eslint-disable no-undef */

let api = null;
let library = 0;
let renderer = 0;
let track = 0;
let canvas = null;
let context = null;
let fontsAttached = 0;

// libass packs a colour as 0xRRGGBBAA and its alpha is INVERSE: 0 is opaque.
// Reading it the other way around renders every sign as a solid block, which
// looks like a broken renderer rather than a misread byte.
function blend(target, image, width) {
	const bitmapW = image.w;
	const bitmapH = image.h;
	const stride = image.stride;
	const colour = image.color >>> 0;
	const r = (colour >>> 24) & 0xFF;
	const g = (colour >>> 16) & 0xFF;
	const b = (colour >>> 8) & 0xFF;
	const opacity = 1 - ((colour & 0xFF) / 255);
	if (opacity <= 0)
		return;

	for (let y = 0; y < bitmapH; y++) {
		for (let x = 0; x < bitmapW; x++) {
			const coverage = api.HEAPU8[image.bitmap + y * stride + x];
			if (coverage === 0)
				continue;

			const alpha = (coverage / 255) * opacity;
			const at = ((image.dstY + y) * width + (image.dstX + x)) * 4;
			const inverse = 1 - alpha;

			target[at] = r * alpha + target[at] * inverse;
			target[at + 1] = g * alpha + target[at + 1] * inverse;
			target[at + 2] = b * alpha + target[at + 2] * inverse;
			target[at + 3] = 255 * alpha + target[at + 3] * inverse;
		}
	}
}

// ASS_Image is a linked list, and every field is read by offset because the
// struct has no JS binding. The order is fixed by ass_types.h.
function readImage(pointer) {
	const words = pointer >> 2;
	return {
		w: api.HEAP32[words],
		h: api.HEAP32[words + 1],
		stride: api.HEAP32[words + 2],
		bitmap: api.HEAPU32[words + 3],
		color: api.HEAPU32[words + 4],
		dstX: api.HEAP32[words + 5],
		dstY: api.HEAP32[words + 6],
		next: api.HEAPU32[words + 7],
	};
}

function render(timeMs) {
	if (!renderer || !track || !context)
		return;

	// BigInt, because ass_render_frame takes the timestamp as long long and
	// emscripten maps a 64-bit argument to BigInt. A plain number throws
	// "Cannot convert 11000 to a BigInt" from inside the module, which reads as
	// a broken build rather than a wrong argument type.
	const first = api._ass_render_frame(renderer, track, BigInt(Math.round(timeMs)), 0);
	const frame = context.createImageData(canvas.width, canvas.height);

	let pointer = first >>> 0;
	let drawn = 0;
	while (pointer !== 0) {
		const image = readImage(pointer);
		blend(frame.data, image, canvas.width);
		pointer = image.next;
		drawn++;
	}

	context.putImageData(frame, 0, 0);

	// Reported, because the canvas belongs to the worker once it is transferred
	// and nothing on the main thread can read a pixel back. Without this the
	// difference between "composited four bitmaps" and "drew nothing" is
	// invisible to everything above, which is how a blank overlay gets called a
	// timing problem.
	postMessage({ type: 'nm:rendered', count: drawn, timeMs });
	return drawn;
}

function fail(error) {
	postMessage({ type: 'nm:error', message: String(error && error.message ? error.message : error) });
}

function attachFont(name, bytes) {
	const size = bytes.byteLength;
	const buffer = api._malloc(size);
	api.HEAPU8.set(new Uint8Array(bytes), buffer);
	// libass copies the face, so the allocation is ours to release. Leaking one
	// per font per episode is how a season of anime exhausts a wasm heap.
	api.ccall('ass_add_font', null, ['number', 'string', 'number', 'number'], [library, name, buffer, size]);
	api._free(buffer);
	fontsAttached++;
}

function loadTrack(content) {
	if (track)
		api._ass_free_track(track);

	const bytes = new TextEncoder().encode(content);
	const buffer = api._malloc(bytes.length);
	api.HEAPU8.set(bytes, buffer);
	track = api.ccall('ass_read_memory', 'number', ['number', 'number', 'number', 'number'], [library, buffer, bytes.length, 0]);
	api._free(buffer);

	if (!track)
		throw new Error('libass refused the track');
}

function sizeTo(width, height) {
	canvas.width = width;
	canvas.height = height;
	api._ass_set_frame_size(renderer, width, height);
	api._ass_set_storage_size(renderer, width, height);
}

const handlers = {
	'nm:init': async (msg) => {
		api = await NoMercyLibass();
		library = api._ass_library_init();
		if (!library)
			throw new Error('ass_library_init returned null');

		renderer = api._ass_renderer_init(library);
		if (!renderer)
			throw new Error('ass_renderer_init returned null');

		// The embedded face, and only it. Every other surface in the trio
		// renders from the fonts the manifest names, and a browser resolving a
		// missing family from the machine would be the one platform quietly
		// disagreeing about which typeface a sign is drawn in.
		api.ccall('ass_set_fonts', null, ['number', 'string', 'string', 'number', 'number', 'number'], [renderer, '/fonts/default.ttf', 'sans-serif', 0, 0, 1]);
		api._ass_set_cache_limits(renderer, msg.glyphCacheMax || 0, msg.bitmapCacheMegabytes || 0);

		canvas = msg.canvas;
		context = canvas.getContext('2d');
		sizeTo(msg.width, msg.height);

		postMessage({ type: 'nm:ready' });
	},

	'nm:font': (msg) => {
		attachFont(msg.name, msg.bytes);
	},

	'nm:fonts-done': () => {
		postMessage({ type: 'nm:fonts-loaded', count: fontsAttached });
	},

	'nm:track': (msg) => {
		loadTrack(msg.content);
	},

	'nm:resize': (msg) => {
		sizeTo(msg.width, msg.height);
	},

	'nm:time': (msg) => {
		render(msg.timeMs);
	},

	'nm:free': () => {
		if (track) {
			api._ass_free_track(track);
			track = 0;
		}
		if (context)
			context.clearRect(0, 0, canvas.width, canvas.height);
	},
};

self.onmessage = async (event) => {
	const msg = event.data;
	const handler = handlers[msg && msg.type];
	if (!handler)
		return;

	try {
		await handler(msg);
	}
	catch (error) {
		fail(error);
	}
};
