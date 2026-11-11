# Blender-free CPU atlas and texture transfer prototype

This optional C++17 tool combines pinned upstream libraries with a small custom CPU bake loop:

- **Simplification:** meshoptimizer v1.3 `meshopt_simplifyWithAttributes`, with position fixed and normal/UV attributes included in edge scoring. The error argument is normalized by meshoptimizer relative to the mesh extent; it is not a world-space bound or a cage guarantee.
- **UV atlas:** xatlas (MIT), which creates new UV charts/vertices. Its output `xref` is used to copy the retained low-mesh POSITION/NORMAL and preserve original high-mesh attributes for transfer.
- **Ray lookup:** TinyBVH (MIT), using two-sided bounded rays with interpolated high-mesh normal filtering. The custom rasterizer falls back to the source UV interpolation when projection finds no acceptable source hit.
- **Images:** stb_image/stb_image_write (public-domain or MIT dual licensing). Base-color RGB is filtered in linear light and re-encoded as sRGB; alpha and metallic-roughness channels are treated as linear. G remains roughness and B metallic as required by glTF. The default glTF sampler is REPEAT/LINEAR; unsupported transformed coordinates, image formats, multiple materials, extensions and extra material maps are rejected rather than silently discarded.
- **Gutters:** xatlas padding labels guide same-chart dilation. Chart labels constrain dilation so adjacent chart colors are not intentionally copied across a seam.

The current implementation requests 16 pixels of xatlas chart padding. The requested `resolution` is an xatlas packing scale, so the actual atlas can be larger (the recorded 1,024 request produced 1,592 × 1,592). Pixels outside xatlas chart labels remain transparent black, and the GLB carries no precomputed mip chain. Same-chart dilation and zero cross-chart raster overlap do not prove seam-free filtering after a target renderer generates mipmaps.

Build and test:

```sh
make glb_atlas_bake
./glb_atlas_bake source.glb baked.glb bake-report.txt 4000 1024 0.02 25
./glb_atlas_bake --self-test
python3 tests/test_atlas_bake.py
python3 tools/validate_glb.py baked.glb
```

The resolution parameter is a requested xatlas packing scale, not a promise that the output will be exactly that dimension. The tool reports the actual image dimensions and texel coverage.

## Known limits and QA interpretation

This is an independently implemented prototype, not a Blender/Cycles replacement or certified production baker. xatlas is a widely used atlas library, meshoptimizer a widely used simplifier, and TinyBVH a compact ray-query library; the rasterization, color transfer, ray selection, and gutter dilation are project-specific code, tested on synthetic fixtures and a local sample GLB that is not distributed. The projection is not cage-based: it uses a fixed distance bound and normal filter, then direct-UV fallback. The fallback preserves sampled appearance in a few pixels but does not prove geometric correspondence. Thin/overlapping sheets and high-curvature features remain sensitive to ray choice. No normal, occlusion, emissive, or displacement map transfer is implemented; the program rejects materials that need them. It does not generate mipmaps; padding reduces but does not eliminate downstream mip/filter bleed.

The included six-view preview is a CPU **base-color** diagnostic with simple normal shading, not a PBR renderer. Godot 4.6.3 imported the GLBs but could not read a render texture in headless dummy mode; a dummy X server could not bind local sockets in this environment, so no independent PBR render was obtained. Do not interpret the CPU preview as final appearance validation in a target engine.

## Pinned third-party sources

- xatlas: `jpcy/xatlas` commit `f700c7790aaa030e794b52ba7791a05c085faf0c`, MIT; its embedded upstream notices are retained.
- TinyBVH: `jbikker/tinybvh` commit `c9be3103cc9693b456b0a0353927c11cac7d710f` (v1.9.1), MIT; its embedded upstream notices are retained.
- meshoptimizer: v1.3 commit `9e1f07b159d3cb777f1c67ed31fc11fd117986f4`, MIT.
- stb: `nothings/stb` commit `4e9b368bfc071e97206ea5c6adba68dd0cbf8897`, public-domain or MIT dual license. Exact upstream Git blob IDs: `stb_image.h` `9eedabedc45b3e6fd88fae6f14a160b4d53272ec`; `stb_image_write.h` `e4b32ed1bc32ef9c962acbf47a9d10af01939e08`.

References: [meshoptimizer](https://github.com/zeux/meshoptimizer/tree/v1.3), [xatlas](https://github.com/jpcy/xatlas), [TinyBVH](https://github.com/jbikker/tinybvh), [stb](https://github.com/nothings/stb), [glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html).
