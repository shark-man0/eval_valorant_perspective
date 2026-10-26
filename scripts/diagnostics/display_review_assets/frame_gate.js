async function decodeFrameReady(state, frameId, images, sequence) {
  try { await Promise.all(images.map(image => image.decode())); }
  catch { return false; }
  if (state.displaySequence !== sequence) return false;
  state.loadedFrameId = frameId;
  state.decodedFrames.add(frameId);
  return true;
}
function canRecordFrame(state, frameId) {
  return state.loadedFrameId === frameId;
}
function canAttestFullNative(state, view) {
  return view.all_native_images === true && view.frame_ids.every(id => state.decodedFrames.has(id));
}
