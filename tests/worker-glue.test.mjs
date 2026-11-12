// -----------------------------------------------------------------------------
//  Copyright (c) NoMercy Entertainment
//
//  Licensed under the Apache License, Version 2.0. See LICENSE for details.
//
//  SPDX-License-Identifier: Apache-2.0
// -----------------------------------------------------------------------------
//
// The worker glue against a fake libass module. Run: node --test tests/
//
// The glue is a classic worker script that talks to globals, so it is loaded
// into a vm context with those globals replaced: the wasm module, the canvas
// context and the timer. What these tests pin is the protocol and the pixels
// the glue hands to putImageData, not libass itself.

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const GLUE = readFileSync(new URL('../src/worker-glue.js', import.meta.url), 'utf8');
const WIDTH = 64;
const HEIGHT = 32;
const IMAGE_BASE = 4096;

function layoutImages(api, images) {
	let at = IMAGE_BASE;
	let previous = 0;
	const pointers = [];
	for (const image of images) {
		const bitmap = at;
		api.HEAPU8.fill(image.coverage, bitmap, bitmap + image.w * image.h);
		at += image.w * image.h;
		at = (at + 3) & ~3;
		pointers.push(at);
		const words = at >> 2;
		api.HEAP32[words] = image.w;
		api.HEAP32[words + 1] = image.h;
		api.HEAP32[words + 2] = image.w;
		api.HEAPU32[words + 3] = bitmap;
		api.HEAPU32[words + 4] = image.color;
		api.HEAP32[words + 5] = image.x;
		api.HEAP32[words + 6] = image.y;
		api.HEAPU32[words + 7] = 0;
		if (previous)
			api.HEAPU32[(previous >> 2) + 7] = at;
		previous = at;
		at += 32;
	}
	return pointers[0] ?? 0;
}

// What libass hands back for each call, in order: { changed, images }.
function makeWorker({ frames = [], probe = false, bitmaps = false } = {}) {
	const buffer = new ArrayBuffer(1 << 16);
	let brk = 64;
	const renderCalls = [];
	const api = {
		HEAPU8: new Uint8Array(buffer),
		HEAP32: new Int32Array(buffer),
		HEAPU32: new Uint32Array(buffer),
		_malloc(size) {
			const pointer = brk;
			brk += (size + 7) & ~7;
			return pointer;
		},
		_free() {},
		_ass_library_init: () => 1,
		_ass_renderer_init: () => 2,
		_ass_set_cache_limits() {},
		_ass_set_frame_size() {},
		_ass_set_storage_size() {},
		_ass_free_track() {},
		ccall: name => (name === 'ass_read_memory' ? 3 : 0),
		_ass_render_frame(_renderer, _track, time, detect) {
			const step = frames[renderCalls.length] ?? { changed: 2, images: [] };
			renderCalls.push({ time: Number(time), detect });
			if (detect)
				api.HEAP32[detect >> 2] = step.changed;
			return layoutImages(api, step.images);
		},
	};

	const context = {
		created: [],
		puts: [],
		clears: [],
		createImageData(width, height) {
			const image = { width, height, data: new Uint8ClampedArray(width * height * 4) };
			context.created.push(image);
			return image;
		},
		putImageData(image, ...args) {
			context.puts.push({ args, pixels: Uint8ClampedArray.from(image.data) });
		},
		clearRect(...args) {
			context.clears.push(args);
		},
	};
	const canvas = { width: 0, height: 0, getContext: () => context };

	const posted = [];
	const transfers = [];
	const timers = [];
	const offscreens = [];
	let clock = 0;
	const sandbox = {
		self: {},
		postMessage: (message, list) => {
			posted.push(message);
			transfers.push(list ?? []);
		},
		OffscreenCanvas: class {
			constructor(width, height) {
				this.width = width;
				this.height = height;
				offscreens.push(this);
			}

			getContext() {
				return context;
			}

			transferToImageBitmap() {
				return { bitmap: true, puts: context.puts.length };
			}
		},
		NoMercyLibass: async () => api,
		setTimeout: (fn) => {
			timers.push(fn);
			return timers.length;
		},
		performance: { now: () => (clock += 2) },
		TextEncoder,
		BigInt,
		Math,
		String,
		Error,
	};
	vm.runInNewContext(GLUE, sandbox);

	const worker = {
		api,
		context,
		canvas,
		posted,
		transfers,
		offscreens,
		renderCalls,
		async send(message) {
			await sandbox.self.onmessage({ data: message });
		},
		flush() {
			while (timers.length)
				timers.shift()();
		},
		async time(timeMs) {
			await worker.send({ type: 'nm:time', timeMs });
			worker.flush();
		},
		of: type => posted.filter(message => message.type === type),
	};
	const init = bitmaps
		? { type: 'nm:init', width: WIDTH, height: HEIGHT, probe }
		: { type: 'nm:init', canvas, width: WIDTH, height: HEIGHT, probe };
	return worker.send(init)
		.then(() => worker.send({ type: 'nm:track', content: '[Script Info]' }))
		.then(() => worker);
}

// The old composite, kept as the reference: a fresh zeroed frame per render.
function reference(images) {
	const data = new Uint8ClampedArray(WIDTH * HEIGHT * 4);
	for (const image of images) {
		const r = (image.color >>> 24) & 0xFF;
		const g = (image.color >>> 16) & 0xFF;
		const b = (image.color >>> 8) & 0xFF;
		const opacity = 1 - ((image.color & 0xFF) / 255);
		for (let y = 0; y < image.h; y++) {
			for (let x = 0; x < image.w; x++) {
				const alpha = (image.coverage / 255) * opacity;
				const at = ((image.y + y) * WIDTH + (image.x + x)) * 4;
				// ImageData is straight alpha: weight the old color by the old alpha, divide by the new one.
				const inverse = 1 - alpha;
				const old = data[at + 3] / 255;
				const out = alpha + old * inverse;
				data[at] = (r * alpha + data[at] * old * inverse) / out;
				data[at + 1] = (g * alpha + data[at + 1] * old * inverse) / out;
				data[at + 2] = (b * alpha + data[at + 2] * old * inverse) / out;
				data[at + 3] = 255 * out;
			}
		}
	}
	return data;
}

const RED = { x: 4, y: 2, w: 8, h: 4, color: 0xFF000000, coverage: 255 };
const BLUE = { x: 20, y: 10, w: 6, h: 5, color: 0x0000FF40, coverage: 128 };
const GREEN = { x: 30, y: 20, w: 4, h: 4, color: 0x00FF0000, coverage: 200 };

test('probe off: the worker posts no measurement', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }] });
	await worker.time(1000);
	assert.equal(worker.of('nm:probe').length, 0);
});

test('probe on: every render attempt reports its time, whether it drew and the drop count', async () => {
	const worker = await makeWorker({ probe: true, frames: [{ changed: 2, images: [RED] }, { changed: 0, images: [RED] }] });
	await worker.time(1000);
	await worker.time(1040);
	const probes = worker.of('nm:probe');
	assert.equal(probes.length, 2);
	assert.equal(typeof probes[0].renderMs, 'number');
	assert.ok(probes[0].renderMs > 0);
	assert.equal(probes[0].drew, true);
	assert.equal(probes[1].drew, false);
	assert.equal(probes[1].dropped, 0);
});

test('a burst of 60 time messages renders only the newest and counts 59 drops', async () => {
	const worker = await makeWorker({ probe: true, frames: [{ changed: 2, images: [RED] }] });
	for (let i = 0; i < 60; i++)
		await worker.send({ type: 'nm:time', timeMs: 1000 + i * 16 });
	worker.flush();
	assert.equal(worker.renderCalls.length, 1);
	assert.equal(worker.renderCalls[0].time, 1000 + 59 * 16);
	assert.equal(worker.of('nm:probe')[0].dropped, 59);
});

test('libass is given a change-detection pointer, the same one every call', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }, { changed: 1, images: [RED] }] });
	await worker.time(1000);
	await worker.time(1016);
	assert.notEqual(worker.renderCalls[0].detect, 0);
	assert.equal(worker.renderCalls[1].detect, worker.renderCalls[0].detect);
});

test('an unchanged result skips the composite, the upload and the rendered report', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }, { changed: 0, images: [RED] }, { changed: 1, images: [RED] }] });
	await worker.time(1000);
	await worker.time(1016);
	assert.equal(worker.context.puts.length, 1);
	assert.equal(worker.of('nm:rendered').length, 1);
	await worker.time(1032);
	assert.equal(worker.context.puts.length, 2);
});

test('the first render after a resize draws even when libass reports no change', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }, { changed: 0, images: [RED] }] });
	await worker.time(1000);
	await worker.send({ type: 'nm:resize', width: WIDTH, height: HEIGHT });
	await worker.time(1016);
	assert.equal(worker.context.puts.length, 2);
});

test('one ImageData serves every frame of the same size and is recreated on resize', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }, { changed: 2, images: [GREEN] }, { changed: 2, images: [RED] }] });
	await worker.time(1000);
	await worker.time(1016);
	assert.equal(worker.context.created.length, 1);
	await worker.send({ type: 'nm:resize', width: 32, height: 16 });
	await worker.time(1032);
	assert.equal(worker.context.created.length, 2);
});

test('every upload is the whole frame at the origin, with no dirty rectangle', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED, BLUE] }, { changed: 2, images: [GREEN] }] });
	await worker.time(1000);
	await worker.time(1016);
	assert.deepEqual(worker.context.puts[0].args, [0, 0]);
	assert.deepEqual(worker.context.puts[1].args, [0, 0]);
});

test('the pixels equal the old full-frame composite, including after content goes away', async () => {
	const sequence = [[RED, BLUE], [GREEN], [], [BLUE, RED]];
	const worker = await makeWorker({ frames: sequence.map(images => ({ changed: 2, images })) });
	for (let i = 0; i < sequence.length; i++) {
		await worker.time(1000 + i * 16);
		assert.deepEqual(worker.context.puts[i].pixels, reference(sequence[i]), `frame ${i}`);
	}
});

test('half-coverage white on an empty frame keeps full white and carries the coverage in alpha', async () => {
	const edge = { x: 4, y: 2, w: 2, h: 2, color: 0xFFFFFF00, coverage: 128 };
	const worker = await makeWorker({ frames: [{ changed: 2, images: [edge] }] });
	await worker.time(1000);
	const at = (2 * WIDTH + 4) * 4;
	assert.deepEqual([...worker.context.puts[0].pixels.slice(at, at + 4)], [255, 255, 255, 128]);
});

test('a frame with no images after drawn content uploads a cleared frame', async () => {
	const worker = await makeWorker({ frames: [{ changed: 2, images: [RED] }, { changed: 2, images: [] }] });
	await worker.time(1000);
	await worker.time(1016);
	assert.deepEqual(worker.context.puts[1].args, [0, 0]);
	assert.ok(worker.context.puts[1].pixels.every(byte => byte === 0));
});

// Bitmap mode: no canvas is transferred; each nm:frame request is answered with an ImageBitmap.
const frameRequest = (timeMs, seq = 1, epoch = 1) => ({ type: 'nm:frame', timeMs, seq, epoch });

test('bitmap mode makes its own offscreen canvas of the given size and posts nm:ready', async () => {
	const worker = await makeWorker({ bitmaps: true });
	assert.equal(worker.offscreens.length, 1);
	assert.deepEqual([worker.offscreens[0].width, worker.offscreens[0].height], [WIDTH, HEIGHT]);
	assert.equal(worker.of('nm:ready').length, 1);
});

test('nm:frame renders every request in order and never coalesces', async () => {
	const worker = await makeWorker({ bitmaps: true, frames: [{ changed: 2, images: [RED] }] });
	for (let i = 0; i < 60; i++)
		await worker.send(frameRequest(1000 + i * 42, i));
	assert.equal(worker.renderCalls.length, 60);
	assert.deepEqual(worker.renderCalls.map(call => call.time), Array.from({ length: 60 }, (_, i) => 1000 + i * 42));
	assert.equal(worker.of('nm:frame').length, 60);
});

test('a drawn frame is answered with a transferred bitmap carrying its time, seq and epoch', async () => {
	const worker = await makeWorker({ bitmaps: true, frames: [{ changed: 2, images: [RED] }] });
	await worker.send(frameRequest(1042, 7, 3));
	const [reply] = worker.of('nm:frame');
	assert.equal(reply.result, 'drawn');
	assert.deepEqual([reply.timeMs, reply.seq, reply.epoch], [1042, 7, 3]);
	assert.equal(reply.bitmap.bitmap, true);
	const list = worker.transfers[worker.posted.indexOf(reply)];
	assert.equal(list.length, 1);
	assert.equal(list[0], reply.bitmap);
});

test('an unchanged frame is answered "same" and an image-free frame "empty", both without a bitmap', async () => {
	const worker = await makeWorker({ bitmaps: true, frames: [{ changed: 2, images: [RED] }, { changed: 0, images: [RED] }, { changed: 2, images: [] }] });
	await worker.send(frameRequest(1000, 1));
	await worker.send(frameRequest(1042, 2));
	await worker.send(frameRequest(1084, 3));
	const replies = worker.of('nm:frame');
	assert.deepEqual(replies.map(r => r.result), ['drawn', 'same', 'empty']);
	assert.equal(replies[1].bitmap, undefined);
	assert.equal(replies[2].bitmap, undefined);
});

test('a forced frame draws again even when libass reports no change', async () => {
	const worker = await makeWorker({ bitmaps: true, frames: [{ changed: 2, images: [RED] }, { changed: 0, images: [RED] }] });
	await worker.send(frameRequest(1000, 1));
	await worker.send({ ...frameRequest(1042, 2), force: true });
	assert.deepEqual(worker.of('nm:frame').map(r => r.result), ['drawn', 'drawn']);
});

test('the pixels in bitmap mode equal the full-frame composite', async () => {
	const worker = await makeWorker({ bitmaps: true, frames: [{ changed: 2, images: [RED, BLUE] }] });
	await worker.send(frameRequest(1000));
	assert.deepEqual(worker.context.puts[0].pixels, reference([RED, BLUE]));
});
