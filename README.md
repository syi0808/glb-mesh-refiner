# glb-mesh-refiner

A standalone C++17 prototype for reducing one indexed triangle primitive in an embedded-texture glTF binary (GLB). It uses area-weighted Garland–Heckbert quadric error metrics and conservatively rejects collapses that violate geometry, topology, UV orientation/stretch, shading-normal, or sampled source-UV correspondence checks.

The tool retains the original face-corner attributes through render-vertex splits. UV seam endpoints can be simplified only by a paired, synchronized geometric collapse: both chart wedges receive the same new position while their UVs and normals are interpolated independently. Ambiguous seam groups, open boundaries, pinned small components, and flagged needle-like faces remain protected. Both collapse stages transactionally reject any exact-position face/edge-use change that creates or worsens duplicate geometric faces or edges with more than two uses. The implementation is experimental and does not promise a requested triangle count.

## Build and test

Requires a C++17 compiler. Python 3, NumPy, Pillow, and SciPy are needed for the test and optional validation utilities.

```sh
make
./glb_refine source.glb refined.glb 4000 report.tsv 0.004 1.25 0.8660254037844386
python3 tools/validate_glb.py refined.glb --source source.glb
make test
```

The final three arguments are the source-UV geometric envelope limit in world units, maximum relative UV directional stretch, and minimum source-normal cosine. They are conservative rejection thresholds, not certified geometric bounds.

## Limits

- Supports one mesh with one indexed triangle primitive and float POSITION, NORMAL, and TEXCOORD_0 attributes. Unsupported attributes, animation, skinning, morph targets, extensions, sparse accessors, or multiple primitives are rejected rather than silently discarded.
- UV seam detection uses exact coincident input positions as an analysis topology. It does not weld original chart vertices or claim to be a complete implementation of a published seam-decimation algorithm.
- The sampled UV-to-source-surface envelope is heuristic, not a continuous error proof. It does not evaluate per-texel color continuity across seams.
- One primitive has one material. Material JSON and embedded images are preserved by the GLB writer, but byte equality alone does not guarantee identical appearance in every renderer.
- The requested face count is a target; safety constraints can stop early.

See `docs/uv-envelope.md`, `docs/uv-seam-collapse.md`, and `docs/references.md` for implementation details and sources.
